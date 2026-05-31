import pytest

from app.core.redis import check_redis
from app.db.health import check_database


@pytest.mark.anyio
async def test_check_database_returns_false_for_invalid_database_url():
    ok = await check_database("postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid")

    assert ok is False


@pytest.mark.anyio
async def test_check_redis_returns_false_for_invalid_redis_url():
    ok = await check_redis("redis://127.0.0.1:1/0")

    assert ok is False
