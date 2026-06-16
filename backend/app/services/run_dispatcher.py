"""
Async run dispatcher using Celery.

Enqueues individual eval_case tasks to the Celery worker pool,
then polls for completion. Replaces the synchronous execute_run().
"""

from __future__ import annotations

import logging

from celery import chord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import new_uuid, utc_now
from app.models import (
    AppVersion,
    EvalCase,
    EvalRun,
    EvalRunItem,
    EvalSuite,
    EvalSuiteCase,
    EvaluatorConfig,
)
from app.workers.celery_app import (
    celery_app,  # noqa: F401 — register Celery app before task imports
)
from app.workers.tasks import check_run_completion, run_eval_case

logger = logging.getLogger("evalforge.run_dispatcher")


async def dispatch_run(
    session: AsyncSession,
    app_version_id: str,
    suite_id: str,
    evaluator_config_id: str,
    case_ids: list[str] | None = None,
) -> EvalRun:
    """
    Create an EvalRun and dispatch all case eval tasks to Celery workers.

    Args:
        session: Async DB session.
        app_version_id: Version to evaluate.
        suite_id: Suite containing cases.
        evaluator_config_id: Which evaluators to run.
        case_ids: Optional subset of cases. If None, runs all cases in the suite.

    Returns:
        The created EvalRun (status='running').
    """
    # Validate entities exist
    version = await session.get(AppVersion, app_version_id)
    suite = await session.get(EvalSuite, suite_id)
    evaluator_config = await session.get(EvaluatorConfig, evaluator_config_id)

    if version is None:
        raise ValueError("App version not found")
    if suite is None:
        raise ValueError("Eval suite not found")
    if evaluator_config is None:
        raise ValueError("Evaluator config not found")

    # Load cases
    cases = await _load_suite_cases(session, suite_id, case_ids)
    if not cases:
        raise ValueError("No cases found in suite")

    # Create the run
    run = EvalRun(
        id=new_uuid(),
        app_version_id=app_version_id,
        suite_id=suite_id,
        evaluator_config_id=evaluator_config_id,
        status="running",
        started_at=utc_now(),
        case_count=len(cases),
    )
    session.add(run)
    await session.flush()

    # Create run items and dispatch tasks
    task_signatures = []
    for case in cases:
        item = EvalRunItem(
            id=new_uuid(),
            run_id=run.id,
            case_id=case.id,
            status="queued",
        )
        session.add(item)
        await session.flush()

        # Create Celery task signature
        task_signatures.append(
            run_eval_case.s(
                run_item_id=item.id,
                case_id=case.id,
                version_id=app_version_id,
                evaluator_config_id=evaluator_config_id,
            )
        )

    await session.commit()

    # Dispatch all tasks as a Celery chord so the run is finalized after workers finish.
    if task_signatures:
        job = chord(task_signatures, check_run_completion.s(run_id=run.id))
        job.apply_async()
        logger.info(
            "Dispatched %d eval tasks for run=%s",
            len(task_signatures),
            run.id,
        )

    await session.refresh(run)
    return run


async def dispatch_run_sync(
    session: AsyncSession,
    app_version_id: str,
    suite_id: str,
    evaluator_config_id: str,
    case_ids: list[str] | None = None,
) -> EvalRun:
    """
    Synchronous fallback — runs eval cases in-process without Celery.

    Used when Redis/Celery is unavailable (e.g., local dev without Docker).
    """
    from app.services.run_executor import execute_run

    return await execute_run(
        session=session,
        app_version_id=app_version_id,
        suite_id=suite_id,
        evaluator_config_id=evaluator_config_id,
        case_ids=case_ids,
    )


async def _load_suite_cases(
    session: AsyncSession,
    suite_id: str,
    case_ids: list[str] | None = None,
) -> list[EvalCase]:
    """Load cases belonging to a suite, optionally filtered by case_ids."""
    statement = (
        select(EvalCase)
        .join(EvalSuiteCase, EvalSuiteCase.case_id == EvalCase.id)
        .where(EvalSuiteCase.suite_id == suite_id)
        .order_by(EvalCase.created_at.asc())
    )
    if case_ids is not None:
        statement = statement.where(EvalCase.id.in_(case_ids))
    result = await session.scalars(statement)
    return list(result)
