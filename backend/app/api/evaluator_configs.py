from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import EvaluatorConfig
from app.schemas import EvaluatorConfigCreate, EvaluatorConfigRead

router = APIRouter(prefix="/api/evaluator-configs", tags=["evaluator-configs"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=EvaluatorConfigRead, status_code=status.HTTP_201_CREATED)
async def create_evaluator_config(
    payload: EvaluatorConfigCreate,
    session: SessionDep,
) -> EvaluatorConfig:
    existing = await session.scalar(
        select(EvaluatorConfig).where(EvaluatorConfig.name == payload.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluator config name already exists",
        )

    config = EvaluatorConfig(name=payload.name, config=payload.config)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.get("", response_model=list[EvaluatorConfigRead])
async def list_evaluator_configs(
    session: SessionDep,
) -> list[EvaluatorConfig]:
    result = await session.scalars(
        select(EvaluatorConfig).order_by(EvaluatorConfig.created_at.desc())
    )
    return list(result)
