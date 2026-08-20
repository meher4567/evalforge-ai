from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ORGANIZATION_SLUG = "default"

ROLE_LEVELS = {
    "viewer": 10,
    "evaluator": 20,
    "admin": 30,
    "owner": 40,
}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str | None
    organization_id: str
    role: str
    authentication_type: str
    session_id: str | None = None
    api_key_id: str | None = None


def require_role(principal: Principal, minimum_role: str) -> None:
    from fastapi import HTTPException, status

    if ROLE_LEVELS.get(principal.role, -1) < ROLE_LEVELS[minimum_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {minimum_role} or higher is required",
        )
