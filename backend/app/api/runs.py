from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models import EvalResult, EvalRun, EvalRunItem, Trace
from app.schemas import RunCreate, RunItemRead, RunRead, TraceRead
from app.services.run_executor import execute_run

router = APIRouter(prefix="/api/runs", tags=["runs"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreate, session: SessionDep) -> EvalRun:
    settings = get_settings()
    try:
        if settings.run_mode == "celery":
            from app.services.run_dispatcher import dispatch_run

            return await dispatch_run(
                session,
                app_version_id=payload.app_version_id,
                suite_id=payload.suite_id,
                evaluator_config_id=payload.evaluator_config_id,
                case_ids=payload.case_ids,
            )

        return await execute_run(
            session,
            app_version_id=payload.app_version_id,
            suite_id=payload.suite_id,
            evaluator_config_id=payload.evaluator_config_id,
            case_ids=payload.case_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=list[RunRead])
async def list_runs(session: SessionDep) -> list[EvalRun]:
    result = await session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()))
    return list(result)


@router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: str, session: SessionDep) -> EvalRun:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/items", response_model=list[RunItemRead])
async def list_run_items(run_id: str, session: SessionDep) -> list[RunItemRead]:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    item_rows = list(
        await session.scalars(
            select(EvalRunItem)
            .where(EvalRunItem.run_id == run_id)
            .order_by(EvalRunItem.case_id.asc())
        )
    )
    response: list[RunItemRead] = []
    for item in item_rows:
        result_rows = list(
            await session.scalars(
                select(EvalResult)
                .where(EvalResult.run_item_id == item.id)
                .order_by(EvalResult.created_at.asc())
            )
        )
        response.append(
            RunItemRead(
                id=item.id,
                run_id=item.run_id,
                case_id=item.case_id,
                status=item.status,
                attempt_count=item.attempt_count,
                recorded_latency_ms=item.recorded_latency_ms,
                recorded_cost_usd=float(item.recorded_cost_usd)
                if item.recorded_cost_usd is not None
                else None,
                error_message=item.error_message,
                started_at=item.started_at,
                completed_at=item.completed_at,
                results=[
                    {
                        "id": result.id,
                        "evaluator_name": result.evaluator_name,
                        "score": float(result.score) if result.score is not None else None,
                        "passed": result.passed,
                        "errored": result.errored,
                        "skipped": result.skipped,
                        "error_message": result.error_message,
                        "details": result.details,
                        "created_at": result.created_at,
                    }
                    for result in result_rows
                ],
            )
        )
    return response


@router.get("/{run_id}/traces/{case_id}", response_model=TraceRead)
async def get_trace(run_id: str, case_id: str, session: SessionDep) -> Trace:
    item = await session.scalar(
        select(EvalRunItem).where(EvalRunItem.run_id == run_id, EvalRunItem.case_id == case_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run item not found")

    trace = await session.scalar(select(Trace).where(Trace.run_item_id == item.id))
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return trace
