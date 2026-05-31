from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import EvalCase, EvalSuite, EvalSuiteCase
from app.schemas import (
    EvalCaseImportRequest,
    EvalCaseImportResult,
    EvalCaseRead,
    EvalSuiteSummary,
)

router = APIRouter(prefix="/api/suites", tags=["eval-suites"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TagQuery = Annotated[str | None, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.post(
    "/{suite_id}/cases/import",
    response_model=EvalCaseImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_eval_cases(
    suite_id: str,
    payload: EvalCaseImportRequest,
    session: SessionDep,
) -> EvalCaseImportResult:
    suite = await session.get(EvalSuite, suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found")

    errors: list[str] = []
    imported = 0
    for index, case_payload in enumerate(payload.cases):
        if "input" not in case_payload.payload:
            errors.append(f"case[{index}] missing payload.input")
            continue

        case = EvalCase(
            external_id=case_payload.external_id,
            payload=case_payload.payload,
        )
        session.add(case)
        await session.flush()
        session.add(EvalSuiteCase(suite_id=suite_id, case_id=case.id))
        imported += 1

    await session.commit()
    return EvalCaseImportResult(imported=imported, errors=errors)


@router.get("/{suite_id}/cases", response_model=list[EvalCaseRead])
async def list_eval_cases(
    suite_id: str,
    session: SessionDep,
    tag: TagQuery = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> list[EvalCase]:
    suite = await session.get(EvalSuite, suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found")

    result = await session.scalars(
        select(EvalCase)
        .join(EvalSuiteCase, EvalSuiteCase.case_id == EvalCase.id)
        .where(EvalSuiteCase.suite_id == suite_id)
        .order_by(EvalCase.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    cases = list(result)
    if tag is not None:
        cases = [case for case in cases if tag in case.payload.get("tags", [])]
    return cases


@router.get("/{suite_id}/summary", response_model=EvalSuiteSummary)
async def get_eval_suite_summary(
    suite_id: str,
    session: SessionDep,
) -> EvalSuiteSummary:
    suite = await session.get(EvalSuite, suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found")

    result = await session.scalars(
        select(EvalCase)
        .join(EvalSuiteCase, EvalSuiteCase.case_id == EvalCase.id)
        .where(EvalSuiteCase.suite_id == suite_id)
    )
    cases = list(result)
    tags = Counter(tag for case in cases for tag in case.payload.get("tags", []))
    return EvalSuiteSummary(case_count=len(cases), tag_distribution=dict(sorted(tags.items())))
