from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.tenancy import Principal, require_role
from app.db.session import get_session
from app.models import GateRule
from app.schemas import GateRuleCreate, GateRuleRead
from app.services.comparison import validate_gate_rules

router = APIRouter(prefix="/api/gate-rules", tags=["gate-rules"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=GateRuleRead, status_code=status.HTTP_201_CREATED)
async def create_gate_rule(
    payload: GateRuleCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> GateRule:
    require_role(principal, "evaluator")
    existing = await session.scalar(
        select(GateRule).where(
            GateRule.organization_id == principal.organization_id,
            GateRule.name == payload.name,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Gate rule name already exists"
        )

    try:
        rules = validate_gate_rules(payload.rules)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    gate_rule = GateRule(
        organization_id=principal.organization_id,
        name=payload.name,
        rules=rules,
    )
    session.add(gate_rule)
    await session.commit()
    await session.refresh(gate_rule)
    return gate_rule


@router.get("", response_model=list[GateRuleRead])
async def list_gate_rules(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[GateRule]:
    result = await session.scalars(
        select(GateRule)
        .where(GateRule.organization_id == principal.organization_id)
        .order_by(GateRule.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/{gate_rule_id}", response_model=GateRuleRead)
async def get_gate_rule(
    gate_rule_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> GateRule:
    gate_rule = await session.scalar(
        select(GateRule).where(
            GateRule.id == gate_rule_id,
            GateRule.organization_id == principal.organization_id,
        )
    )
    if gate_rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gate rules not found")
    return gate_rule
