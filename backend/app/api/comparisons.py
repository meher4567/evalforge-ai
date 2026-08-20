from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.tenancy import Principal, require_role
from app.db.session import get_session
from app.models import Comparison, RegressionReport
from app.schemas import CIGateReportRead, ComparisonCreate, ComparisonRead, GateDecisionRead
from app.services.ci_gate_report import build_ci_gate_report
from app.services.comparison import compute_comparison

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=ComparisonRead, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    payload: ComparisonCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonRead:
    require_role(principal, "evaluator")
    try:
        comparison, report = await compute_comparison(
            session,
            baseline_run_id=payload.baseline_run_id,
            candidate_run_id=payload.candidate_run_id,
            gate_rules_id=payload.gate_rules_id,
            organization_id=principal.organization_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return build_comparison_response(comparison, report)


@router.get("", response_model=list[ComparisonRead])
async def list_comparisons(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ComparisonRead]:
    comparisons = list(
        await session.scalars(
            select(Comparison)
            .where(Comparison.organization_id == principal.organization_id)
            .order_by(Comparison.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    comparison_ids = [comparison.id for comparison in comparisons]
    reports = (
        list(
            await session.scalars(
                select(RegressionReport).where(RegressionReport.comparison_id.in_(comparison_ids))
            )
        )
        if comparison_ids
        else []
    )
    reports_by_comparison = {report.comparison_id: report for report in reports}
    return [
        build_comparison_response(comparison, reports_by_comparison[comparison.id])
        for comparison in comparisons
        if comparison.id in reports_by_comparison
    ]


@router.get("/{comparison_id}", response_model=ComparisonRead)
async def get_comparison(
    comparison_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonRead:
    comparison = await _tenant_comparison(session, comparison_id, principal.organization_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    report = await session.scalar(
        select(RegressionReport).where(RegressionReport.comparison_id == comparison_id)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regression report not found"
        )
    return build_comparison_response(comparison, report)


@router.get("/{comparison_id}/gate-decision", response_model=GateDecisionRead)
async def get_gate_decision(
    comparison_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> GateDecisionRead:
    if await _tenant_comparison(session, comparison_id, principal.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    report = await session.scalar(
        select(RegressionReport).where(RegressionReport.comparison_id == comparison_id)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regression report not found"
        )
    return GateDecisionRead(verdict=report.gate_verdict, reasons=report.gate_reasons)


@router.get("/{comparison_id}/ci-report", response_model=CIGateReportRead)
async def get_ci_gate_report(
    comparison_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    dashboard_url: str | None = None,
    fail_on_warn: bool = False,
) -> CIGateReportRead:
    comparison = await _tenant_comparison(session, comparison_id, principal.organization_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    report = await session.scalar(
        select(RegressionReport).where(RegressionReport.comparison_id == comparison_id)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Regression report not found"
        )

    return CIGateReportRead(
        **build_ci_gate_report(
            comparison=comparison,
            report=report,
            dashboard_url=dashboard_url,
            fail_on_warn=fail_on_warn,
        )
    )


async def _tenant_comparison(
    session: AsyncSession,
    comparison_id: str,
    organization_id: str,
) -> Comparison | None:
    return await session.scalar(
        select(Comparison).where(
            Comparison.id == comparison_id,
            Comparison.organization_id == organization_id,
        )
    )


def build_comparison_response(
    comparison: Comparison,
    report: RegressionReport,
) -> ComparisonRead:
    return ComparisonRead(
        id=comparison.id,
        baseline_run_id=comparison.baseline_run_id,
        candidate_run_id=comparison.candidate_run_id,
        gate_rules_id=comparison.gate_rules_id,
        status=comparison.status,
        created_at=comparison.created_at,
        report={
            "id": report.id,
            "comparison_id": report.comparison_id,
            "metrics": report.metrics,
            "gate_verdict": report.gate_verdict,
            "gate_reasons": report.gate_reasons,
            "created_at": report.created_at,
        },
    )
