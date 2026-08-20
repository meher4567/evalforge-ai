import asyncio

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.redis import check_redis
from app.db.health import check_database, check_database_schema

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    api: bool
    database: bool
    redis: bool
    schema_ready: bool = Field(serialization_alias="schema")


class LivenessResponse(BaseModel):
    status: str
    api: bool


@router.get("/livez", response_model=LivenessResponse)
async def livez() -> LivenessResponse:
    return LivenessResponse(status="ok", api=True)


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return await _dependency_health()


@router.get(
    "/readyz",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readyz(response: Response) -> HealthResponse:
    health = await _dependency_health()
    if health.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health


async def _dependency_health() -> HealthResponse:
    settings = get_settings()
    database_ok, redis_ok, schema_ok = await asyncio.gather(
        check_database(settings.database_url),
        check_redis(settings.redis_url),
        check_database_schema(settings.database_url),
    )

    return HealthResponse(
        status="ok" if database_ok and redis_ok and schema_ok else "degraded",
        api=True,
        database=database_ok,
        redis=redis_ok,
        schema_ready=schema_ok,
    )
