import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def check_database(database_url: str | None = None) -> bool:
    settings = get_settings()
    engine = create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
    )

    try:
        async with asyncio.timeout(settings.health_check_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()
