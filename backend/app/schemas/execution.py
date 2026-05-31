from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunCreate(BaseModel):
    app_version_id: str
    suite_id: str
    evaluator_config_id: str
    case_ids: list[str] | None = None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    app_version_id: str
    suite_id: str
    evaluator_config_id: str
    status: str
    case_count: int
    case_completed: int
    case_errored: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EvalResultRead(BaseModel):
    id: str
    evaluator_name: str
    score: float | None
    passed: bool | None
    errored: bool
    skipped: bool
    error_message: str | None
    details: dict[str, Any]
    created_at: datetime


class RunItemRead(BaseModel):
    id: str
    run_id: str
    case_id: str
    status: str
    attempt_count: int
    recorded_latency_ms: int | None
    recorded_cost_usd: float | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    results: list[EvalResultRead]


class TraceRead(BaseModel):
    id: str
    run_item_id: str
    payload: dict[str, Any]
    created_at: datetime


class ComparisonCreate(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    gate_rules_id: str | None = None


class RegressionReportRead(BaseModel):
    id: str
    comparison_id: str
    metrics: dict[str, Any]
    gate_verdict: str
    gate_reasons: list[dict[str, Any]]
    created_at: datetime


class ComparisonRead(BaseModel):
    id: str
    baseline_run_id: str
    candidate_run_id: str
    gate_rules_id: str
    status: str
    created_at: datetime
    report: RegressionReportRead


class GateDecisionRead(BaseModel):
    verdict: str
    reasons: list[dict[str, Any]]
