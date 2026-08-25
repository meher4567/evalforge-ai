"""
Celery worker tasks for async eval execution.

Each task executes ONE eval case against ONE app version:
1. Load case + version from DB
2. Call the app adapter
3. Run all configured evaluators
4. Store trace + results
5. Recount run progress from authoritative item states

Retry semantics:
- Transient errors (connection, timeout) trigger automatic retry.
- Permanent errors (missing entities, bad adapter) fail immediately.
- Counters are derived only after final completion or final failure,
  never during a retry loop.
- Duplicate task delivery is protected by worker leases and terminal items are skipped.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import and_, create_engine, or_, text, update
from sqlalchemy.orm import Session

from app.adapters.loader import load_adapter
from app.core.config import get_settings
from app.db.base import utc_now
from app.evaluators.engine import evaluate_case
from app.models import (
    AppVersion,
    EvalCase,
    EvalResult,
    EvalRunItem,
    EvaluatorConfig,
    Trace,
)
from app.services.run_executor import redact_sensitive_config

logger = get_task_logger(__name__)

settings = get_settings()

# Sync engine for worker tasks (Celery workers use sync code)
# Convert asyncpg URL to psycopg2 format
_SYNC_DATABASE_URL = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+asyncpg", "postgresql+psycopg2"
)

_engine = create_engine(_SYNC_DATABASE_URL, pool_size=5, max_overflow=10)
TERMINAL_ITEM_STATUSES = frozenset({"completed", "errored", "timed_out", "cancelled"})
TASK_LEASE_SECONDS = 240


@shared_task(
    bind=True,
    name="evalforge.eval_case",
    max_retries=2,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=30,
)
def run_eval_case(
    self,
    run_item_id: str,
    case_id: str,
    version_id: str,
    evaluator_config_id: str,
) -> dict:
    """
    Execute a single eval case asynchronously.

    Args:
        run_item_id: ID of the EvalRunItem row.
        case_id: ID of the EvalCase.
        version_id: ID of the AppVersion to evaluate against.
        evaluator_config_id: ID of the EvaluatorConfig to use.

    Returns:
        dict with status and summary info.
    """
    logger.info(
        "Starting eval case: run_item=%s case=%s version=%s attempt=%d",
        run_item_id,
        case_id,
        version_id,
        self.request.retries + 1,
    )

    with Session(_engine) as session:
        run_item: EvalRunItem | None = None
        try:
            run_item = session.get(EvalRunItem, run_item_id)
            if run_item is None:
                raise ValueError(f"Run item {run_item_id} not found")

            if run_item.status in TERMINAL_ITEM_STATUSES:
                logger.info(
                    "Run item %s is already terminal (%s), skipping",
                    run_item_id,
                    run_item.status,
                )
                return {"status": "skipped", "reason": f"already_{run_item.status}"}

            task_id = str(self.request.id or f"manual:{run_item_id}")
            if not _claim_run_item(
                session,
                run_item_id=run_item_id,
                task_id=task_id,
                attempt_count=self.request.retries + 1,
            ):
                logger.info("Run item %s is owned by another active worker", run_item_id)
                return {"status": "skipped", "reason": "already_in_progress"}

            # Load remaining entities after this delivery owns the item lease.
            run_item = session.get(EvalRunItem, run_item_id)
            case = session.get(EvalCase, case_id)
            version = session.get(AppVersion, version_id)
            evaluator_config = session.get(EvaluatorConfig, evaluator_config_id)

            if case is None:
                raise ValueError(f"Case {case_id} not found")
            if version is None:
                raise ValueError(f"Version {version_id} not found")
            if evaluator_config is None:
                raise ValueError(f"Evaluator config {evaluator_config_id} not found")
            # ── Clean up partial results from a previous retry ──
            if self.request.retries > 0:
                logger.info(
                    "Retry attempt %d for run_item=%s — clearing stale data",
                    self.request.retries + 1,
                    run_item_id,
                )
                _clear_stale_data(session, run_item_id)

            # Extract question from case payload
            question = _extract_question(case.payload)

            # Load and call adapter
            adapter = load_adapter(version.adapter_module)
            logger.debug(
                "Calling adapter %s with question: %s...",
                version.adapter_module,
                question[:80],
            )
            output = adapter(question, version.config)

            # Record latency and cost
            run_item.recorded_latency_ms = output.latency_ms
            run_item.recorded_cost_usd = output.estimated_cost_usd
            run_item.status = "completed"
            run_item.completed_at = utc_now()
            run_item.lease_expires_at = None

            # Store trace
            trace = Trace(
                run_item_id=run_item.id,
                payload={
                    "input": case.payload.get("input", {}),
                    "version_config": redact_sensitive_config(version.config),
                    "steps": output.trace_steps,
                    "output": {
                        "answer": output.answer,
                        "retrieved_chunks": output.retrieved_chunks,
                    },
                    "metadata": {
                        "adapter_module": version.adapter_module,
                        "model_used": output.model_used,
                        "prompt_used": output.prompt_used,
                        "latency_ms": output.latency_ms,
                        "estimated_cost_usd": output.estimated_cost_usd,
                    },
                },
            )
            session.add(trace)

            # Run evaluators
            evaluator_results = evaluate_case(case.payload, output, evaluator_config.config)
            for result in evaluator_results:
                eval_result = EvalResult(
                    run_item_id=run_item.id,
                    evaluator_name=result.evaluator_name,
                    score=result.score,
                    passed=result.passed,
                    errored=result.errored,
                    skipped=result.skipped,
                    error_message=result.error_message,
                    details=asdict(result).get("details", {}),
                )
                session.add(eval_result)

            session.commit()

            # Recount from terminal rows so retries and duplicate delivery cannot
            # inflate progress counters.
            _refresh_run_progress(session, run_item.run_id)

            logger.info(
                "Completed eval case: run_item=%s latency_ms=%d cost_usd=%s evaluators=%d",
                run_item_id,
                output.latency_ms,
                output.estimated_cost_usd,
                len(evaluator_results),
            )

            return {
                "status": "completed",
                "run_item_id": run_item_id,
                "latency_ms": output.latency_ms,
                "evaluator_count": len(evaluator_results),
            }

        except Exception as exc:
            session.rollback()
            logger.error(
                "Eval case failed: run_item=%s error=%s attempt=%d",
                run_item_id,
                exc,
                self.request.retries + 1,
            )

            # Determine if error is transient (retryable)
            if _is_transient_error(exc) and self.request.retries < self.max_retries:
                logger.info(
                    "Retrying eval case (transient error): run_item=%s attempt=%d/%d",
                    run_item_id,
                    self.request.retries + 1,
                    self.max_retries,
                )
                # Do NOT mark as errored or increment counters before retry
                raise self.retry(exc=exc) from exc

            # ── Final failure: no more retries ──
            logger.error(
                "Eval case permanently failed: run_item=%s error=%s",
                run_item_id,
                exc,
            )

            final_item = session.get(EvalRunItem, run_item_id)
            if final_item is not None and final_item.status not in TERMINAL_ITEM_STATUSES:
                final_item.status = "errored"
                final_item.error_message = str(exc)[:1000]
                final_item.completed_at = utc_now()
                final_item.lease_expires_at = None
                final_item.attempt_count = self.request.retries + 1
                session.commit()
                _refresh_run_progress(session, final_item.run_id)

            # A header task must return so the Celery chord always invokes the
            # authoritative completion callback. The item row remains errored.
            return {
                "status": "errored",
                "run_item_id": run_item_id,
                "error": str(exc)[:1000],
            }


@shared_task(name="evalforge.check_run_completion")
def check_run_completion(
    chord_results: list[dict] | None = None,
    run_id: str | None = None,
) -> dict:
    """
    Check if all items in a run are complete and update run status.

    Celery chords pass the header result list as the first positional callback
    argument, while EvalForge supplies run_id as a keyword.
    """
    if run_id is None and isinstance(chord_results, str):
        run_id = chord_results

    if run_id is None:
        logger.warning("Run completion callback invoked without run_id")
        return {"status": "unknown"}

    with Session(_engine) as session:
        result = session.execute(
            text(
                "SELECT count(*) as total, "
                "sum(case when status = 'completed' then 1 else 0 end) as completed, "
                "sum(case when status in ('errored', 'timed_out', 'cancelled') "
                "then 1 else 0 end) as errored "
                "FROM eval_run_items WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        )
        row = result.first()
        if row is None:
            return {"status": "unknown"}

        total, completed, errored = (int(value or 0) for value in row)

        if total == 0:
            logger.warning("Run %s has no items to finalize", run_id)
            return {"status": "unknown", "completed": 0, "errored": 0}

        if completed + errored >= total:
            new_status = "completed" if errored == 0 else "partial"
            session.execute(
                text(
                    "UPDATE eval_runs SET status = :status, case_completed = :completed, "
                    "case_errored = :errored, completed_at = :now "
                    "WHERE id = :run_id"
                ),
                {
                    "status": new_status,
                    "completed": completed,
                    "errored": errored,
                    "now": utc_now(),
                    "run_id": run_id,
                },
            )
            session.commit()
            logger.info(
                "Run %s completed: status=%s completed=%d errored=%d",
                run_id,
                new_status,
                completed,
                errored,
            )
            return {"status": new_status, "completed": completed, "errored": errored}

        return {"status": "running", "completed": completed, "errored": errored}


def _extract_question(case_payload: dict) -> str:
    """Extract the question string from a case payload."""
    raw_input = case_payload.get("input", "")
    if isinstance(raw_input, dict):
        return str(raw_input.get("question", ""))
    return str(raw_input)


def _claim_run_item(
    session: Session,
    *,
    run_item_id: str,
    task_id: str,
    attempt_count: int,
) -> bool:
    """Atomically claim an item unless another live task delivery owns it."""
    now = utc_now()
    claim = session.execute(
        update(EvalRunItem)
        .where(
            EvalRunItem.id == run_item_id,
            or_(
                EvalRunItem.status == "queued",
                and_(
                    EvalRunItem.status == "running",
                    or_(
                        EvalRunItem.worker_task_id == task_id,
                        EvalRunItem.lease_expires_at.is_(None),
                        EvalRunItem.lease_expires_at < now,
                    ),
                ),
            ),
        )
        .values(
            status="running",
            worker_task_id=task_id,
            lease_expires_at=now + timedelta(seconds=TASK_LEASE_SECONDS),
            attempt_count=attempt_count,
            started_at=now,
            completed_at=None,
            error_message=None,
        )
    )
    session.commit()
    return bool(claim.rowcount)


def _refresh_run_progress(session: Session, run_id: str) -> None:
    """Set progress counters from authoritative item states."""
    session.execute(
        text(
            "UPDATE eval_runs SET "
            "case_completed = (SELECT count(*) FROM eval_run_items "
            "WHERE run_id = :run_id AND status = 'completed'), "
            "case_errored = (SELECT count(*) FROM eval_run_items "
            "WHERE run_id = :run_id AND status IN ('errored', 'timed_out', 'cancelled')) "
            "WHERE id = :run_id"
        ),
        {"run_id": run_id},
    )
    session.commit()


def _clear_stale_data(session: Session, run_item_id: str) -> None:
    """Delete stale traces and evaluator results from a previous failed attempt."""
    session.execute(
        text("DELETE FROM eval_results WHERE run_item_id = :rid"),
        {"rid": run_item_id},
    )
    session.execute(
        text("DELETE FROM traces WHERE run_item_id = :rid"),
        {"rid": run_item_id},
    )
    session.commit()


def _is_transient_error(exc: Exception) -> bool:
    """Determine if an error is transient (worth retrying)."""
    error_str = str(exc).lower()
    transient_keywords = [
        "connection",
        "timeout",
        "temporarily unavailable",
        "too many connections",
        "connection refused",
        "operationalerror",
    ]
    return any(keyword in error_str for keyword in transient_keywords)
