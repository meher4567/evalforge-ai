from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.tenancy import Principal
from app.db.session import get_session
from app.services.dashboard_aggregation import build_latest_dashboard_snapshot
from app.services.dashboard_snapshot import load_demo_dashboard_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/demo")
async def get_demo_dashboard_snapshot(
    _principal: Annotated[Principal, Depends(get_current_principal)],
):
    snapshot = load_demo_dashboard_snapshot()
    snapshot["dataSource"] = "demo"
    snapshot["comparisonId"] = None
    snapshot["benchmarkSummary"].setdefault("projectName", "Demo RAG QA")
    snapshot["benchmarkSummary"].setdefault("suiteName", "demo_rag_500")
    return snapshot


@router.get("/latest")
async def get_latest_dashboard_snapshot(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    comparison_id: str | None = None,
    failure_limit: Annotated[int, Query(ge=1, le=200)] = 50,
    failure_offset: Annotated[int, Query(ge=0)] = 0,
):
    snapshot = await build_latest_dashboard_snapshot(
        session,
        comparison_id=comparison_id,
        failure_limit=failure_limit,
        failure_offset=failure_offset,
        organization_id=principal.organization_id,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No computed comparisons found")
    return snapshot
