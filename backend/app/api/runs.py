from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.config import get_settings
from app.core.observability import RUNS_CREATED
from app.core.tenancy import Principal, require_role
from app.db.session import get_session
from app.models import EvalResult, EvalRun, EvalRunItem, Trace
from app.schemas import RunCreate, RunItemRead, RunRead, TraceRead
from app.services.errors import DispatchError, InvalidRunRequestError, ResourceNotFoundError
from app.services.run_dispatcher import dispatch_run
from app.services.run_executor import execute_run

router = APIRouter(prefix="/api/runs", tags=["runs"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> EvalRun:
    require_role(principal, "evaluator")
    settings = get_settings()
    try:
        runner = dispatch_run if settings.run_mode == "celery" else execute_run
        run = await runner(
            session,
            app_version_id=payload.app_version_id,
            suite_id=payload.suite_id,
            evaluator_config_id=payload.evaluator_config_id,
            case_ids=payload.case_ids,
            organization_id=principal.organization_id,
        )
        RUNS_CREATED.labels(mode=settings.run_mode).inc()
        return run
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidRunRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except DispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": str(exc), "run_id": exc.run_id},
        ) from exc


@router.get("", response_model=list[RunRead])
async def list_runs(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EvalRun]:
    result = await session.scalars(
        select(EvalRun)
        .where(EvalRun.organization_id == principal.organization_id)
        .order_by(EvalRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: str, principal: PrincipalDep, session: SessionDep) -> EvalRun:
    run = await _tenant_run(session, run_id, principal.organization_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/items", response_model=list[RunItemRead])
async def list_run_items(
    run_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RunItemRead]:
    run = await _tenant_run(session, run_id, principal.organization_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    item_rows = list(
        await session.scalars(
            select(EvalRunItem)
            .where(EvalRunItem.run_id == run_id)
            .order_by(EvalRunItem.case_id.asc())
            .limit(limit)
            .offset(offset)
        )
    )
    item_ids = [item.id for item in item_rows]
    all_results = (
        list(
            await session.scalars(
                select(EvalResult)
                .where(EvalResult.run_item_id.in_(item_ids))
                .order_by(EvalResult.created_at.asc())
            )
        )
        if item_ids
        else []
    )
    results_by_item: dict[str, list[EvalResult]] = {}
    for result in all_results:
        results_by_item.setdefault(result.run_item_id, []).append(result)
    response: list[RunItemRead] = []
    for item in item_rows:
        result_rows = results_by_item.get(item.id, [])
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
async def get_trace(
    run_id: str,
    case_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> Trace:
    if await _tenant_run(session, run_id, principal.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    item = await session.scalar(
        select(EvalRunItem).where(EvalRunItem.run_id == run_id, EvalRunItem.case_id == case_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run item not found")

    trace = await session.scalar(select(Trace).where(Trace.run_item_id == item.id))
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return trace


async def _tenant_run(
    session: AsyncSession,
    run_id: str,
    organization_id: str,
) -> EvalRun | None:
    return await session.scalar(
        select(EvalRun).where(
            EvalRun.id == run_id,
            EvalRun.organization_id == organization_id,
        )
    )
