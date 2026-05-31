from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.dashboard_aggregation import build_latest_dashboard_snapshot
from app.services.dashboard_snapshot import load_demo_dashboard_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/demo")
async def get_demo_dashboard_snapshot():
    return load_demo_dashboard_snapshot()


@router.get("/latest")
async def get_latest_dashboard_snapshot(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    snapshot = await build_latest_dashboard_snapshot(session)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No computed comparisons found")
    return snapshot
