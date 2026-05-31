import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.redis import check_redis
from app.db.health import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    api: bool
    database: bool
    redis: bool


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    settings = get_settings()
    database_ok, redis_ok = await asyncio.gather(
        check_database(settings.database_url),
        check_redis(settings.redis_url),
    )

    return HealthResponse(
        status="ok" if database_ok and redis_ok else "degraded",
        api=True,
        database=database_ok,
        redis=redis_ok,
    )
