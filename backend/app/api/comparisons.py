from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Comparison, RegressionReport
from app.schemas import CIGateReportRead, ComparisonCreate, ComparisonRead, GateDecisionRead
from app.services.ci_gate_report import build_ci_gate_report
from app.services.comparison import compute_comparison

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=ComparisonRead, status_code=status.HTTP_201_CREATED)
async def create_comparison(payload: ComparisonCreate, session: SessionDep) -> ComparisonRead:
    try:
        comparison, report = await compute_comparison(
            session,
            baseline_run_id=payload.baseline_run_id,
            candidate_run_id=payload.candidate_run_id,
            gate_rules_id=payload.gate_rules_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return build_comparison_response(comparison, report)


@router.get("/{comparison_id}", response_model=ComparisonRead)
async def get_comparison(comparison_id: str, session: SessionDep) -> ComparisonRead:
    comparison = await session.get(Comparison, comparison_id)
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
async def get_gate_decision(comparison_id: str, session: SessionDep) -> GateDecisionRead:
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
    session: SessionDep,
    dashboard_url: str | None = None,
    fail_on_warn: bool = False,
) -> CIGateReportRead:
    comparison = await session.get(Comparison, comparison_id)
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
