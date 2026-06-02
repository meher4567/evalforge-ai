"""
Celery worker tasks for async eval execution.

Each task executes ONE eval case against ONE app version:
1. Load case + version from DB
2. Call the app adapter
3. Run all configured evaluators
4. Store trace + results
5. Update run counters atomically

Retry semantics:
- Transient errors (connection, timeout) trigger automatic retry.
- Permanent errors (missing entities, bad adapter) fail immediately.
- Counters are only incremented on final completion or final failure,
  never during a retry loop.
- Duplicate task delivery is safe: completed items are skipped.
"""

from __future__ import annotations

from dataclasses import asdict

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, text
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

logger = get_task_logger(__name__)

settings = get_settings()

# Sync engine for worker tasks (Celery workers use sync code)
# Convert asyncpg URL to psycopg2 format
_SYNC_DATABASE_URL = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+asyncpg", "postgresql+psycopg2"
)

_engine = create_engine(_SYNC_DATABASE_URL, pool_size=5, max_overflow=10)


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
        try:
            # Load entities
            case = session.get(EvalCase, case_id)
            version = session.get(AppVersion, version_id)
            evaluator_config = session.get(EvaluatorConfig, evaluator_config_id)
            run_item = session.get(EvalRunItem, run_item_id)

            if case is None:
                raise ValueError(f"Case {case_id} not found")
            if version is None:
                raise ValueError(f"Version {version_id} not found")
            if evaluator_config is None:
                raise ValueError(f"Evaluator config {evaluator_config_id} not found")
            if run_item is None:
                raise ValueError(f"Run item {run_item_id} not found")

            # ── Idempotency: skip already-completed items ──
            if run_item.status == "completed":
                logger.info("Run item %s already completed, skipping", run_item_id)
                return {"status": "skipped", "reason": "already_completed"}

            # ── Clean up partial results from a previous retry ──
            if self.request.retries > 0:
                logger.info(
                    "Retry attempt %d for run_item=%s — clearing stale data",
                    self.request.retries + 1,
                    run_item_id,
                )
                _clear_stale_data(session, run_item_id)

            # Mark as running and increment attempt count
            run_item.status = "running"
            run_item.started_at = utc_now()
            run_item.attempt_count = self.request.retries + 1
            session.commit()

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

            # Store trace
            trace = Trace(
                run_item_id=run_item.id,
                payload={
                    "input": case.payload.get("input", {}),
                    "version_config": version.config,
                    "steps": output.trace_steps,
                    "output": {
                        "answer": output.answer,
                        "retrieved_chunks": output.retrieved_chunks,
                    },
                    "metadata": {
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

            # Atomically update the run's completion counter
            _increment_run_counter(session, run_item.run_id, completed=True)

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

            if run_item is not None:
                run_item.status = "errored"
                run_item.error_message = str(exc)[:1000]
                run_item.completed_at = utc_now()
                run_item.attempt_count = self.request.retries + 1
                session.commit()
                # Only increment errored counter on final failure
                _increment_run_counter(session, run_item.run_id, completed=False, errored=True)

            # Re-raise so Celery records the final failure
            raise


@shared_task(name="evalforge.check_run_completion")
def check_run_completion(run_id: str) -> dict:
    """
    Check if all items in a run are complete and update run status.

    Called after each eval_case task completes (via callback).
    """
    with Session(_engine) as session:
        result = session.execute(
            text(
                "SELECT count(*) as total, "
                "sum(case when status = 'completed' then 1 else 0 end) as completed, "
                "sum(case when status = 'errored' or status = 'timed_out' "
                "then 1 else 0 end) as errored "
                "FROM eval_run_items WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        )
        row = result.first()
        if row is None:
            return {"status": "unknown"}

        total, completed, errored = row

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


def _increment_run_counter(
    session: Session,
    run_id: str,
    *,
    completed: bool = False,
    errored: bool = False,
) -> None:
    """Atomically increment the run's counter fields."""
    set_clauses = []
    if completed:
        set_clauses.append("case_completed = case_completed + 1")
    if errored:
        set_clauses.append("case_errored = case_errored + 1")

    if set_clauses:
        session.execute(
            text(f"UPDATE eval_runs SET {', '.join(set_clauses)} WHERE id = :run_id"),
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
