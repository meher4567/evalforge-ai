from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import get_current_principal
from app.core.tenancy import Principal
from app.evaluators.engine import evaluator_capabilities
from app.schemas import EvaluatorCapabilityRead

router = APIRouter(prefix="/api/evaluators", tags=["evaluators"])


@router.get("", response_model=list[EvaluatorCapabilityRead])
async def list_evaluators(
    _principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[dict]:
    return evaluator_capabilities()
