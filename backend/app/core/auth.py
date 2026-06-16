from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_key(
    x_evalforge_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    expected_key = get_settings().api_key
    if not expected_key:
        return

    supplied_key = x_evalforge_api_key or _bearer_token(authorization)
    if supplied_key and hmac.compare_digest(supplied_key, expected_key):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid EvalForge API key required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token
