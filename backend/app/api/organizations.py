from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.tenancy import Principal, require_role
from app.db.session import get_session
from app.models import Membership, Organization, User
from app.schemas import (
    MemberCreate,
    MemberRead,
    MemberRoleUpdate,
    OrganizationCreate,
    OrganizationMembershipRead,
    OrganizationRead,
)
from app.services.authentication import hash_password

router = APIRouter(prefix="/api/organizations", tags=["organizations"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.get("", response_model=list[OrganizationMembershipRead])
async def list_organizations(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[OrganizationMembershipRead]:
    user_id = _require_user_id(principal)
    rows = (
        await session.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id == user_id)
            .order_by(Organization.name, Organization.slug)
        )
    ).all()
    return [
        OrganizationMembershipRead(organization=organization, role=membership.role)
        for membership, organization in rows
    ]


@router.get("/current", response_model=OrganizationRead)
async def current_organization(
    principal: PrincipalDep,
    session: SessionDep,
) -> Organization:
    organization = await session.get(Organization, principal.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization not found",
        )
    return organization


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> Organization:
    user_id = _require_user_id(principal)
    if await session.scalar(select(Organization).where(Organization.slug == payload.slug)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )
    organization = Organization(name=payload.name, slug=payload.slug)
    session.add(organization)
    await session.flush()
    session.add(
        Membership(
            user_id=user_id,
            organization_id=organization.id,
            role="owner",
        )
    )
    await session.commit()
    await session.refresh(organization)
    return organization


@router.get("/current/members", response_model=list[MemberRead])
async def list_members(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[MemberRead]:
    rows = (
        await session.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == principal.organization_id)
            .order_by(User.email)
        )
    ).all()
    return [
        MemberRead(user=user, role=membership.role, joined_at=membership.created_at)
        for membership, user in rows
    ]


@router.post(
    "/current/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    payload: MemberCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> MemberRead:
    require_role(principal, "admin")
    if payload.role == "owner":
        require_role(principal, "owner")

    user = await session.scalar(select(User).where(User.email == payload.email))
    if user is None:
        if payload.password is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A temporary password is required when creating a new user",
            )
        user = User(
            email=payload.email,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
        )
        session.add(user)
        await session.flush()
    elif user.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is disabled")

    membership = await session.get(Membership, (principal.organization_id, user.id))
    if membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        )
    membership = Membership(
        user_id=user.id,
        organization_id=principal.organization_id,
        role=payload.role,
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return MemberRead(user=user, role=membership.role, joined_at=membership.created_at)


@router.patch("/current/members/{user_id}", response_model=MemberRead)
async def update_member(
    user_id: str,
    payload: MemberRoleUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> MemberRead:
    require_role(principal, "admin")
    membership = await _membership_or_404(session, principal.organization_id, user_id)
    if membership.role == "owner" or payload.role == "owner":
        require_role(principal, "owner")
    if membership.role == "owner" and payload.role != "owner":
        await _ensure_not_last_owner(session, principal.organization_id)
    membership.role = payload.role
    await session.commit()
    user = await session.get(User, user_id)
    assert user is not None
    return MemberRead(user=user, role=membership.role, joined_at=membership.created_at)


@router.delete("/current/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> None:
    require_role(principal, "admin")
    membership = await _membership_or_404(session, principal.organization_id, user_id)
    if membership.role == "owner":
        require_role(principal, "owner")
        await _ensure_not_last_owner(session, principal.organization_id)
    await session.delete(membership)
    await session.commit()


def _require_user_id(principal: Principal) -> str:
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires a user credential",
        )
    return principal.user_id


async def _membership_or_404(
    session: AsyncSession,
    organization_id: str,
    user_id: str,
) -> Membership:
    membership = await session.get(Membership, (organization_id, user_id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return membership


async def _ensure_not_last_owner(session: AsyncSession, organization_id: str) -> None:
    owner_count = await session.scalar(
        select(func.count(Membership.user_id)).where(
            Membership.organization_id == organization_id,
            Membership.role == "owner",
        )
    )
    if owner_count is None or owner_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization must retain at least one owner",
        )
