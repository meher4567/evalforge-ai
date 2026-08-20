import pytest

from app.core.redis import check_redis
from app.db.health import check_database, check_database_schema, expected_schema_revision


@pytest.mark.anyio
async def test_check_database_returns_false_for_invalid_database_url():
    ok = await check_database(
        "postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid",
        timeout_seconds=0.1,
    )

    assert ok is False


@pytest.mark.anyio
async def test_check_redis_returns_false_for_invalid_redis_url():
    ok = await check_redis("redis://127.0.0.1:1/0", timeout_seconds=0.1)

    assert ok is False


@pytest.mark.anyio
async def test_check_database_schema_returns_false_for_unreachable_database():
    ok = await check_database_schema(
        "postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid",
        timeout_seconds=0.1,
    )

    assert ok is False


def test_expected_schema_revision_is_current_alembic_head():
    assert expected_schema_revision() == "20260820_0004"
