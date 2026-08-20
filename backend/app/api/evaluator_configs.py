from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.tenancy import Principal, require_role
from app.db.session import get_session
from app.evaluators.engine import validate_evaluator_config
from app.models import EvaluatorConfig
from app.schemas import EvaluatorConfigCreate, EvaluatorConfigRead

router = APIRouter(prefix="/api/evaluator-configs", tags=["evaluator-configs"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=EvaluatorConfigRead, status_code=status.HTTP_201_CREATED)
async def create_evaluator_config(
    payload: EvaluatorConfigCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> EvaluatorConfig:
    require_role(principal, "evaluator")
    existing = await session.scalar(
        select(EvaluatorConfig).where(
            EvaluatorConfig.organization_id == principal.organization_id,
            EvaluatorConfig.name == payload.name,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluator config name already exists",
        )

    try:
        validated_config = validate_evaluator_config(payload.config)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    config = EvaluatorConfig(
        organization_id=principal.organization_id,
        name=payload.name,
        config=validated_config,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.get("", response_model=list[EvaluatorConfigRead])
async def list_evaluator_configs(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EvaluatorConfig]:
    result = await session.scalars(
        select(EvaluatorConfig)
        .where(EvaluatorConfig.organization_id == principal.organization_id)
        .order_by(EvaluatorConfig.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)
