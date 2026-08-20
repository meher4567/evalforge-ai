import asyncio
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def check_database(
    database_url: str | None = None,
    timeout_seconds: float | None = None,
) -> bool:
    settings = get_settings()
    engine = create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
    )

    try:
        async with asyncio.timeout(timeout_seconds or settings.health_check_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def check_database_schema(
    database_url: str | None = None,
    timeout_seconds: float | None = None,
) -> bool:
    settings = get_settings()
    engine = create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
    )

    try:
        async with asyncio.timeout(timeout_seconds or settings.health_check_timeout_seconds):
            async with engine.connect() as connection:
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        return revision == expected_schema_revision()
    except Exception:
        return False
    finally:
        await engine.dispose()


@lru_cache(maxsize=1)
def expected_schema_revision() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise RuntimeError("Alembic migration head is unavailable")
    return head
