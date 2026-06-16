from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.loader import load_adapter
from app.db.base import utc_now
from app.evaluators.engine import evaluate_case
from app.models import (
    AppVersion,
    EvalCase,
    EvalResult,
    EvalRun,
    EvalRunItem,
    EvalSuite,
    EvalSuiteCase,
    EvaluatorConfig,
    Trace,
)

SENSITIVE_CONFIG_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


async def execute_run(
    session: AsyncSession,
    app_version_id: str,
    suite_id: str,
    evaluator_config_id: str,
    case_ids: list[str] | None = None,
) -> EvalRun:
    version = await session.get(AppVersion, app_version_id)
    suite = await session.get(EvalSuite, suite_id)
    evaluator_config = await session.get(EvaluatorConfig, evaluator_config_id)
    if version is None:
        raise ValueError("App version not found")
    if suite is None:
        raise ValueError("Eval suite not found")
    if evaluator_config is None:
        raise ValueError("Evaluator config not found")

    cases = await load_suite_cases(session, suite_id, case_ids)
    adapter = load_adapter(version.adapter_module)
    now = utc_now()

    run = EvalRun(
        app_version_id=app_version_id,
        suite_id=suite_id,
        evaluator_config_id=evaluator_config_id,
        status="running",
        started_at=now,
        case_count=len(cases),
    )
    session.add(run)
    await session.flush()

    completed = 0
    errored = 0
    for case in cases:
        item = EvalRunItem(
            run_id=run.id,
            case_id=case.id,
            status="running",
            started_at=utc_now(),
        )
        session.add(item)
        await session.flush()

        try:
            question = extract_question(case.payload)
            output = adapter(question, version.config)
            item.recorded_latency_ms = output.latency_ms
            item.recorded_cost_usd = output.estimated_cost_usd
            item.status = "completed"
            item.completed_at = utc_now()
            completed += 1

            session.add(
                Trace(
                    run_item_id=item.id,
                    payload={
                        "input": case.payload.get("input", {}),
                        "version_config": redact_sensitive_config(version.config),
                        "steps": output.trace_steps,
                        "output": {
                            "answer": output.answer,
                            "retrieved_chunks": output.retrieved_chunks,
                        },
                        "metadata": {
                            "model_used": output.model_used,
                            "prompt_used": output.prompt_used,
                            "latency_ms": output.latency_ms,
                            "estimated_cost_usd": output.estimated_cost_usd,
                        },
                    },
                )
            )

            for result in evaluate_case(case.payload, output, evaluator_config.config):
                session.add(
                    EvalResult(
                        run_item_id=item.id,
                        evaluator_name=result.evaluator_name,
                        score=result.score,
                        passed=result.passed,
                        errored=result.errored,
                        skipped=result.skipped,
                        error_message=result.error_message,
                        details=asdict(result)["details"],
                    )
                )
        except Exception as exc:
            item.status = "errored"
            item.error_message = str(exc)
            item.completed_at = utc_now()
            errored += 1

    run.case_completed = completed
    run.case_errored = errored
    run.completed_at = utc_now()
    run.status = "completed" if errored == 0 else "partial"
    await session.commit()
    await session.refresh(run)
    return run


async def load_suite_cases(
    session: AsyncSession,
    suite_id: str,
    case_ids: list[str] | None = None,
) -> list[EvalCase]:
    statement = (
        select(EvalCase)
        .join(EvalSuiteCase, EvalSuiteCase.case_id == EvalCase.id)
        .where(EvalSuiteCase.suite_id == suite_id)
        .order_by(EvalCase.created_at.asc())
    )
    if case_ids is not None:
        statement = statement.where(EvalCase.id.in_(case_ids))
    result = await session.scalars(statement)
    return list(result)


def extract_question(case_payload: dict) -> str:
    raw_input = case_payload.get("input", "")
    if isinstance(raw_input, dict):
        return str(raw_input.get("question", ""))
    return str(raw_input)


def redact_sensitive_config(value):
    if isinstance(value, dict):
        redacted = {}
        for key, nested_value in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_CONFIG_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_config(nested_value)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_config(item) for item in value]
    return value
