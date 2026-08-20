from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenancy import DEFAULT_ORGANIZATION_ID, Principal
from app.db.session import get_session
from app.models import AuthSession, Membership, PersonalApiKey, User
from app.services.authentication import hash_token, is_expired

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_principal(
    session: SessionDep,
    x_evalforge_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    settings = get_settings()
    supplied_key = x_evalforge_api_key or _bearer_token(authorization)

    if supplied_key and settings.api_key and hmac.compare_digest(supplied_key, settings.api_key):
        return Principal(
            user_id=None,
            organization_id=DEFAULT_ORGANIZATION_ID,
            role="owner",
            authentication_type="system_api_key",
        )

    if supplied_key:
        principal = await _authenticate_opaque_token(session, supplied_key)
        if principal is not None:
            return principal
        raise _authentication_error()

    if not settings.api_key and settings.environment != "production":
        return Principal(
            user_id=None,
            organization_id=DEFAULT_ORGANIZATION_ID,
            role="owner",
            authentication_type="development",
        )

    raise _authentication_error()


async def require_api_key(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> None:
    """Compatibility dependency for routes that only require authentication."""

    del principal


async def _authenticate_opaque_token(session: AsyncSession, token: str) -> Principal | None:
    token_hash = hash_token(token)
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    )
    if auth_session is not None:
        if auth_session.revoked_at is not None or is_expired(auth_session.expires_at):
            return None
        membership = await _active_membership(
            session,
            auth_session.user_id,
            auth_session.organization_id,
        )
        if membership is None:
            return None
        return Principal(
            user_id=auth_session.user_id,
            organization_id=auth_session.organization_id,
            role=membership.role,
            authentication_type="session",
            session_id=auth_session.id,
        )

    api_key = await session.scalar(
        select(PersonalApiKey).where(PersonalApiKey.token_hash == token_hash)
    )
    if api_key is None or api_key.revoked_at is not None or is_expired(api_key.expires_at):
        return None
    membership = await _active_membership(
        session,
        api_key.user_id,
        api_key.organization_id,
    )
    if membership is None:
        return None
    from app.db.base import utc_now

    api_key.last_used_at = utc_now()
    await session.commit()
    return Principal(
        user_id=api_key.user_id,
        organization_id=api_key.organization_id,
        role=membership.role,
        authentication_type="personal_api_key",
        api_key_id=api_key.id,
    )


async def _active_membership(
    session: AsyncSession,
    user_id: str,
    organization_id: str,
) -> Membership | None:
    row = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            User.status == "active",
        )
    )
    result = row.first()
    return result[0] if result else None


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid EvalForge credentials required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token
