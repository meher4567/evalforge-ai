import asyncio

from redis.asyncio import Redis

from app.core.config import get_settings


async def check_redis(redis_url: str | None = None) -> bool:
    settings = get_settings()
    client = Redis.from_url(
        redis_url or settings.redis_url,
        decode_responses=True,
    )

    try:
        async with asyncio.timeout(settings.health_check_timeout_seconds):
            return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
