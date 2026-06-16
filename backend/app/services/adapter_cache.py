"""
Adapter output cache for EvalForge AI.

Caches adapter outputs to avoid re-running the same (case, version) combinations.
Cache key: SHA-256(case_input + sorted_version_config_json).
TTL: 24 hours.
Skip cache when: --no-cache flag, case tagged 'nondeterministic'.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("evalforge.adapter_cache")

CACHE_TTL_HOURS = 24


def compute_cache_key(case_input: str, version_config: dict) -> str:
    """
    Compute a deterministic cache key from case input + version config.

    Uses SHA-256 over the concatenation of normalized inputs.
    """
    config_json = json.dumps(version_config, sort_keys=True, default=str)
    combined = f"{case_input}|||{config_json}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def get_cached_output(
    session: AsyncSession,
    cache_key: str,
) -> dict | None:
    """
    Retrieve a cached adapter output if it exists and hasn't expired.

    Returns None on cache miss or expiry.
    """
    result = await session.execute(
        text("SELECT output_json, created_at FROM adapter_output_cache WHERE cache_key = :key"),
        {"key": cache_key},
    )
    row = result.first()
    if row is None:
        return None

    output_json, created_at = row
    if created_at is not None:
        age = datetime.now(UTC) - created_at.replace(tzinfo=UTC)
        if age > timedelta(hours=CACHE_TTL_HOURS):
            logger.debug("Cache expired for key %s (age: %s)", cache_key[:16], age)
            return None

    logger.debug("Cache hit for key %s", cache_key[:16])
    return output_json if isinstance(output_json, dict) else json.loads(output_json)


async def set_cached_output(
    session: AsyncSession,
    cache_key: str,
    output: dict,
) -> None:
    """
    Store adapter output in cache. Upserts on cache_key.
    """
    await session.execute(
        text(
            "INSERT INTO adapter_output_cache (cache_key, output_json, created_at) "
            "VALUES (:key, :output::jsonb, :now) "
            "ON CONFLICT (cache_key) DO UPDATE SET "
            "output_json = EXCLUDED.output_json, created_at = EXCLUDED.created_at"
        ),
        {
            "key": cache_key,
            "output": json.dumps(output, default=str),
            "now": datetime.now(UTC),
        },
    )
    await session.flush()
    logger.debug("Cached output for key %s", cache_key[:16])
