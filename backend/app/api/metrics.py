from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import get_settings

router = APIRouter(tags=["operations"])


@router.get("/metrics", include_in_schema=False)
async def metrics(
    authorization: str | None = Header(default=None),
    x_evalforge_metrics_token: str | None = Header(default=None),
) -> Response:
    expected = get_settings().metrics_token
    supplied = x_evalforge_metrics_token or _bearer_token(authorization)
    if expected and (not supplied or not hmac.compare_digest(supplied, expected)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid metrics token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None
