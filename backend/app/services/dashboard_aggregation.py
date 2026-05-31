from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppVersion,
    Comparison,
    EvalCase,
    EvalResult,
    EvalRun,
    EvalRunItem,
    GateRule,
    RegressionReport,
    Trace,
)

METRIC_SPECS = [
    ("pass_rate", "Pass rate", "Pass", "%", "higher", 0.02),
    ("semantic_similarity", "Semantic similarity", "Similarity", "score", "higher", 0.02),
    ("p95_latency_ms", "p95 latency", "p95", "ms", "lower", 50.0),
    ("cost_mean_usd", "Mean cost", "Cost", "usd", "lower", 0.2),
]


async def build_latest_dashboard_snapshot(session: AsyncSession) -> dict[str, Any] | None:
    comparison = await _load_latest_comparison(session)
    if comparison is None:
        return None

    report = await _load_report(session, comparison.id)
    if report is None:
        return None

    baseline = await session.get(EvalRun, comparison.baseline_run_id)
    candidate = await session.get(EvalRun, comparison.candidate_run_id)
    if baseline is None or candidate is None:
        return None

    return {
        "benchmarkSummary": await _build_summary(session, baseline, candidate, report),
        "metrics": _build_metrics(report.metrics, report.gate_reasons),
        "runs": await _build_runs(session, baseline, candidate),
        "traceCases": await _build_trace_cases(session, baseline, candidate),
        "gateRules": await _build_gate_rules(
            session,
            comparison.gate_rules_id,
            report.gate_reasons,
        ),
    }


async def _load_latest_comparison(session: AsyncSession) -> Comparison | None:
    return await session.scalar(
        select(Comparison)
        .where(Comparison.status == "computed")
        .order_by(Comparison.created_at.desc())
        .limit(1)
    )


async def _load_report(session: AsyncSession, comparison_id: str) -> RegressionReport | None:
    return await session.scalar(
        select(RegressionReport).where(RegressionReport.comparison_id == comparison_id)
    )


async def _build_summary(
    session: AsyncSession,
    baseline: EvalRun,
    candidate: EvalRun,
    report: RegressionReport,
) -> dict[str, Any]:
    baseline_version = await session.get(AppVersion, baseline.app_version_id)
    candidate_version = await session.get(AppVersion, candidate.app_version_id)
    elapsed_seconds = _elapsed_seconds(baseline, candidate)
    total_executions = baseline.case_completed + candidate.case_completed

    return {
        "generatedAt": report.created_at.isoformat(),
        "benchmark": "latest_persisted_comparison",
        "baselineVersion": baseline_version.name if baseline_version else baseline.app_version_id,
        "candidateVersion": (
            candidate_version.name if candidate_version else candidate.app_version_id
        ),
        "caseCount": candidate.case_count,
        "totalExecutions": total_executions,
        "elapsedSeconds": elapsed_seconds,
        "casesPerMinute": _cases_per_minute(total_executions, elapsed_seconds),
        "gateVerdict": report.gate_verdict,
    }


def _elapsed_seconds(baseline: EvalRun, candidate: EvalRun) -> float:
    start_times = [
        run.started_at for run in (baseline, candidate) if isinstance(run.started_at, datetime)
    ]
    end_times = [
        run.completed_at for run in (baseline, candidate) if isinstance(run.completed_at, datetime)
    ]
    if not start_times or not end_times:
        return 0.0
    return round((max(end_times) - min(start_times)).total_seconds(), 3)


def _cases_per_minute(total_executions: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return round((total_executions / elapsed_seconds) * 60, 2)


def _build_metrics(
    metrics: dict[str, Any],
    gate_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failing_metrics = {reason["metric"] for reason in gate_reasons}
    return [
        {
            "key": key,
            "label": label,
            "shortLabel": short_label,
            "unit": unit,
            "baseline": _as_float(metrics[key]["baseline_point"]),
            "candidate": _as_float(metrics[key]["candidate_point"]),
            "baselineCi": [
                _as_float(metrics[key]["baseline_ci_lower"]),
                _as_float(metrics[key]["baseline_ci_upper"]),
            ],
            "candidateCi": [
                _as_float(metrics[key]["candidate_ci_lower"]),
                _as_float(metrics[key]["candidate_ci_upper"]),
            ],
            "delta": _as_float(metrics[key]["delta_point"]),
            "deltaCi": [
                _as_float(metrics[key]["delta_ci_lower"]),
                _as_float(metrics[key]["delta_ci_upper"]),
            ],
            "direction": direction,
            "tolerance": tolerance,
            "status": "fail" if key in failing_metrics else "pass",
        }
        for key, label, short_label, unit, direction, tolerance in METRIC_SPECS
    ]


async def _build_runs(
    session: AsyncSession,
    baseline: EvalRun,
    candidate: EvalRun,
) -> list[dict[str, Any]]:
    return [
        await _run_to_dashboard_row(session, candidate),
        await _run_to_dashboard_row(session, baseline),
    ]


async def _run_to_dashboard_row(session: AsyncSession, run: EvalRun) -> dict[str, Any]:
    version = await session.get(AppVersion, run.app_version_id)
    samples = await _collect_run_display_samples(session, run.id)
    return {
        "id": run.id,
        "version": version.name if version else run.app_version_id,
        "suite": run.suite_id,
        "cases": run.case_count,
        "passRate": _average(samples["case_passes"]),
        "semanticSimilarity": _average(samples["semantic_scores"]),
        "p95LatencyMs": max(samples["latencies"], default=0.0),
        "costMeanUsd": _average(samples["costs"]),
        "createdAt": run.created_at.isoformat(),
        "status": run.status,
    }


async def _collect_run_display_samples(
    session: AsyncSession,
    run_id: str,
) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {
        "case_passes": [],
        "semantic_scores": [],
        "latencies": [],
        "costs": [],
    }
    items = list(await session.scalars(select(EvalRunItem).where(EvalRunItem.run_id == run_id)))
    for item in items:
        results = list(
            await session.scalars(select(EvalResult).where(EvalResult.run_item_id == item.id))
        )
        applicable = [
            result
            for result in results
            if not result.skipped and not result.errored and result.passed is not None
        ]
        samples["case_passes"].append(
            1.0 if applicable and all(result.passed for result in applicable) else 0.0
        )
        semantic = _find_result(results, "semantic_similarity")
        if semantic and semantic.score is not None:
            samples["semantic_scores"].append(_as_float(semantic.score))
        if item.recorded_latency_ms is not None:
            samples["latencies"].append(float(item.recorded_latency_ms))
        if item.recorded_cost_usd is not None:
            samples["costs"].append(_as_float(item.recorded_cost_usd))
    return samples


async def _build_trace_cases(
    session: AsyncSession,
    baseline: EvalRun,
    candidate: EvalRun,
) -> list[dict[str, Any]]:
    baseline_by_case = await _load_items_by_case(session, baseline.id)
    candidate_items = list(
        await session.scalars(
            select(EvalRunItem)
            .where(EvalRunItem.run_id == candidate.id)
            .order_by(EvalRunItem.case_id)
        )
    )

    trace_cases: list[dict[str, Any]] = []
    for item in candidate_items:
        results = list(
            await session.scalars(select(EvalResult).where(EvalResult.run_item_id == item.id))
        )
        failed_results = [
            result for result in results if result.passed is False and not result.skipped
        ]
        if not failed_results:
            continue

        case = await session.get(EvalCase, item.case_id)
        trace = await _load_trace(session, item.id)
        baseline_trace = await _load_trace_for_item(session, baseline_by_case.get(item.case_id))
        if case is None or trace is None:
            continue

        trace_cases.append(
            _trace_case_to_dashboard_row(
                case=case,
                item=item,
                trace=trace,
                baseline_trace=baseline_trace,
                results=results,
                failed_result=failed_results[0],
            )
        )

    return sorted(trace_cases, key=lambda trace_case: trace_case["id"])


async def _load_items_by_case(session: AsyncSession, run_id: str) -> dict[str, EvalRunItem]:
    items = list(await session.scalars(select(EvalRunItem).where(EvalRunItem.run_id == run_id)))
    return {item.case_id: item for item in items}


async def _load_trace_for_item(
    session: AsyncSession,
    item: EvalRunItem | None,
) -> Trace | None:
    if item is None:
        return None
    return await _load_trace(session, item.id)


async def _load_trace(session: AsyncSession, run_item_id: str) -> Trace | None:
    return await session.scalar(select(Trace).where(Trace.run_item_id == run_item_id))


def _trace_case_to_dashboard_row(
    case: EvalCase,
    item: EvalRunItem,
    trace: Trace,
    baseline_trace: Trace | None,
    results: list[EvalResult],
    failed_result: EvalResult,
) -> dict[str, Any]:
    semantic = _find_result(results, "semantic_similarity")
    keywords = _find_result(results, "contains_keywords")
    retrieval = _find_result(results, "retrieval_hit_rate")
    payload = case.payload

    return {
        "id": case.external_id or case.id,
        "tag": _first_tag(payload),
        "evaluator": failed_result.evaluator_name,
        "reason": _failure_reason(failed_result),
        "question": _extract_question(payload),
        "expected": str(payload.get("expected_output", "")),
        "baselineAnswer": _trace_answer(baseline_trace),
        "candidateAnswer": _trace_answer(trace),
        "semanticScore": _result_score(semantic),
        "keywordScore": _result_score(keywords),
        "retrievalHit": bool(retrieval.passed) if retrieval else False,
        "latencyMs": item.recorded_latency_ms or 0,
        "costUsd": _as_float(item.recorded_cost_usd or 0),
        "chunks": _trace_chunks(trace),
    }


def _first_tag(payload: dict[str, Any]) -> str:
    tags = payload.get("tags", [])
    if isinstance(tags, list) and tags:
        return str(tags[0])
    return "untagged"


def _extract_question(payload: dict[str, Any]) -> str:
    raw_input = payload.get("input", "")
    if isinstance(raw_input, dict):
        return str(raw_input.get("question", ""))
    return str(raw_input)


def _failure_reason(result: EvalResult) -> str:
    if result.error_message:
        return result.error_message
    return f"{result.evaluator_name} failed"


def _trace_answer(trace: Trace | None) -> str:
    if trace is None:
        return ""
    output = trace.payload.get("output", {})
    if isinstance(output, dict):
        return str(output.get("answer", ""))
    return ""


def _trace_chunks(trace: Trace) -> list[dict[str, Any]]:
    output = trace.payload.get("output", {})
    chunks = output.get("retrieved_chunks", []) if isinstance(output, dict) else []
    if not isinstance(chunks, list):
        return []

    dashboard_chunks: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        dashboard_chunks.append(
            {
                "rank": index,
                "docId": str(chunk.get("doc_id", "")),
                "text": str(chunk.get("text", "")),
                "score": _as_float(chunk.get("score", 0.0)),
            }
        )
    return dashboard_chunks


async def _build_gate_rules(
    session: AsyncSession,
    gate_rules_id: str,
    gate_reasons: list[dict[str, Any]],
) -> list[dict[str, str]]:
    gate_rule = await session.get(GateRule, gate_rules_id)
    reasons_by_metric = {reason["metric"]: reason["verdict"] for reason in gate_reasons}
    if gate_rule is None:
        return []

    return [
        {
            "metric": _metric_label(metric),
            "direction": "higher" if rule.get("direction") == "higher_better" else "lower",
            "tolerance": str(rule.get("tolerance", "")),
            "verdict": reasons_by_metric.get(metric, "pass"),
        }
        for metric, rule in gate_rule.rules.items()
    ]


def _metric_label(metric: str) -> str:
    for key, label, _short_label, _unit, _direction, _tolerance in METRIC_SPECS:
        if key == metric:
            return label
    return metric


def _find_result(results: list[EvalResult], evaluator_name: str) -> EvalResult | None:
    for result in results:
        if result.evaluator_name == evaluator_name:
            return result
    return None


def _result_score(result: EvalResult | None) -> float:
    if result is None or result.score is None:
        return 0.0
    return _as_float(result.score)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def _as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
