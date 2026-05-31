from fastapi import APIRouter

from app.services.dashboard_snapshot import load_demo_dashboard_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/demo")
async def get_demo_dashboard_snapshot():
    return load_demo_dashboard_snapshot()
