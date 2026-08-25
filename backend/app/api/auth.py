from __future__ import annotations

import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.config import get_settings
from app.core.tenancy import Principal
from app.db.base import utc_now
from app.db.session import get_session
from app.models import AuthSession, Membership, Organization, PersonalApiKey, User
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    BootstrapCreate,
    LoginCreate,
    OrganizationSwitch,
    PasswordChange,
    PrincipalRead,
    TokenRead,
)
from app.services.authentication import (
    hash_password,
    is_expired,
    new_api_key,
    new_session_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
DUMMY_PASSWORD_HASH = hash_password("evalforge-invalid-user-timing-value")


@router.post("/bootstrap", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
async def bootstrap(
    payload: BootstrapCreate,
    session: SessionDep,
    bootstrap_token: Annotated[str | None, Header(alias="X-EvalForge-Bootstrap-Token")] = None,
) -> TokenRead:
    expected = get_settings().bootstrap_token
    if not expected or not bootstrap_token or not hmac.compare_digest(bootstrap_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid bootstrap token required",
        )
    if (await session.scalar(select(func.count(User.id)))) != 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap has already been completed",
        )

    organization = await session.scalar(
        select(Organization).where(Organization.slug == payload.organization_slug)
    )
    if organization is None:
        organization = Organization(
            name=payload.organization_name,
            slug=payload.organization_slug,
        )
        session.add(organization)
        await session.flush()

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()
    session.add(
        Membership(
            user_id=user.id,
            organization_id=organization.id,
            role="owner",
        )
    )
    token, token_hash, expires_at = new_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return _token_response(token, expires_at, user, organization, "owner", "session")


@router.post("/login", response_model=TokenRead)
async def login(payload: LoginCreate, session: SessionDep) -> TokenRead:
    user = await session.scalar(select(User).where(User.email == payload.email).with_for_update())
    candidate_hash = (
        user.password_hash
        if user is not None and user.status == "active" and user.password_hash is not None
        else DUMMY_PASSWORD_HASH
    )
    password_valid = verify_password(payload.password, candidate_hash)
    if user is None or user.status != "active":
        raise _invalid_login()

    if user.locked_until is not None and not is_expired(user.locked_until):
        raise _invalid_login()
    if user.locked_until is not None:
        user.locked_until = None
        user.failed_login_attempts = 0
    if not password_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = utc_now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        await session.commit()
        raise _invalid_login()
    user.failed_login_attempts = 0
    user.locked_until = None

    membership_query = (
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id)
        .order_by(Membership.created_at, Organization.slug)
    )
    if payload.organization_slug:
        membership_query = membership_query.where(Organization.slug == payload.organization_slug)
    membership_row = (await session.execute(membership_query)).first()
    if membership_row is None:
        await session.commit()
        raise _invalid_login()
    membership, organization = membership_row

    token, token_hash, expires_at = new_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return _token_response(
        token,
        expires_at,
        user,
        organization,
        membership.role,
        "session",
    )


@router.get("/me", response_model=PrincipalRead)
async def current_principal(principal: PrincipalDep, session: SessionDep) -> PrincipalRead:
    user, organization = await _principal_entities(session, principal)
    return PrincipalRead(
        user=user,
        organization=organization,
        role=principal.role,
        authentication_type=principal.authentication_type,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: PrincipalDep, session: SessionDep) -> None:
    if principal.session_id is not None:
        auth_session = await session.get(AuthSession, principal.session_id)
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = utc_now()
            await session.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    principal: PrincipalDep,
    session: SessionDep,
) -> None:
    user = await _require_user(session, principal)
    if user.password_hash is None or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is invalid",
        )
    user.password_hash = hash_password(payload.new_password)
    other_sessions = await session.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.id != principal.session_id if principal.session_id else True,
        )
    )
    now = utc_now()
    for other_session in other_sessions:
        other_session.revoked_at = now
    await session.commit()


@router.post("/switch-organization", response_model=TokenRead)
async def switch_organization(
    payload: OrganizationSwitch,
    principal: PrincipalDep,
    session: SessionDep,
) -> TokenRead:
    user = await _require_user(session, principal)
    row = (
        await session.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.user_id == user.id,
                Organization.slug == payload.organization_slug,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    membership, organization = row
    token, token_hash, expires_at = new_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return _token_response(
        token,
        expires_at,
        user,
        organization,
        membership.role,
        "session",
    )


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(principal: PrincipalDep, session: SessionDep) -> list[PersonalApiKey]:
    user = await _require_user(session, principal)
    keys = await session.scalars(
        select(PersonalApiKey)
        .where(
            PersonalApiKey.user_id == user.id,
            PersonalApiKey.organization_id == principal.organization_id,
        )
        .order_by(PersonalApiKey.created_at.desc())
    )
    return list(keys)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ApiKeyCreated:
    user = await _require_user(session, principal)
    duplicate = await session.scalar(
        select(PersonalApiKey).where(
            PersonalApiKey.user_id == user.id,
            PersonalApiKey.organization_id == principal.organization_id,
            PersonalApiKey.name == payload.name,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key name already exists in this organization",
        )
    token, prefix, token_hash = new_api_key()
    expires_at = (
        utc_now() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )
    api_key = PersonalApiKey(
        user_id=user.id,
        organization_id=principal.organization_id,
        name=payload.name,
        key_prefix=prefix,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyCreated(
        **ApiKeyRead.model_validate(api_key, from_attributes=True).model_dump(),
        api_key=token,
    )


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> None:
    user = await _require_user(session, principal)
    api_key = await session.scalar(
        select(PersonalApiKey).where(
            PersonalApiKey.id == api_key_id,
            PersonalApiKey.user_id == user.id,
            PersonalApiKey.organization_id == principal.organization_id,
        )
    )
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if api_key.revoked_at is None:
        api_key.revoked_at = utc_now()
        await session.commit()


async def _principal_entities(
    session: AsyncSession, principal: Principal
) -> tuple[User | None, Organization]:
    organization = await session.get(Organization, principal.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization not found",
        )
    user = await session.get(User, principal.user_id) if principal.user_id else None
    return user, organization


async def _require_user(session: AsyncSession, principal: Principal) -> User:
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires a user credential",
        )
    user = await session.get(User, principal.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    return user


def _token_response(
    token: str,
    expires_at,
    user: User,
    organization: Organization,
    role: str,
    authentication_type: str,
) -> TokenRead:
    return TokenRead(
        access_token=token,
        expires_at=expires_at,
        user=user,
        organization=organization,
        role=role,
        authentication_type=authentication_type,
    )


def _invalid_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email, password, or organization",
        headers={"WWW-Authenticate": "Bearer"},
    )
