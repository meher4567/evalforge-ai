from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    App,
    AppVersion,
    Comparison,
    EvalCase,
    EvalResult,
    EvalRun,
    EvalRunItem,
    EvalSuite,
    GateRule,
    RegressionReport,
    Trace,
)
from app.services.statistics import percentile

METRIC_SPECS = [
    ("pass_rate", "Pass rate", "Pass", "%", "higher"),
    ("semantic_similarity", "Token overlap", "Overlap", "score", "higher"),
    ("p95_latency_ms", "p95 latency", "p95", "ms", "lower"),
    ("cost_mean_usd", "Mean cost", "Cost", "usd", "lower"),
]


async def build_latest_dashboard_snapshot(
    session: AsyncSession,
    *,
    comparison_id: str | None = None,
    failure_limit: int = 50,
    failure_offset: int = 0,
    organization_id: str = "00000000-0000-0000-0000-000000000001",
) -> dict[str, Any] | None:
    comparison = await _load_comparison(session, comparison_id, organization_id)
    if comparison is None:
        return None

    report = await _load_report(session, comparison.id)
    if report is None:
        return None

    baseline = await session.get(EvalRun, comparison.baseline_run_id)
    candidate = await session.get(EvalRun, comparison.candidate_run_id)
    if baseline is None or candidate is None:
        return None
    gate_rule = await session.get(GateRule, comparison.gate_rules_id)
    gate_rules = gate_rule.rules if gate_rule is not None else {}

    trace_cases = await _build_trace_cases(session, baseline, candidate)
    paginated_trace_cases = trace_cases[failure_offset : failure_offset + failure_limit]

    return {
        "dataSource": "live",
        "comparisonId": comparison.id,
        "benchmarkSummary": await _build_summary(session, baseline, candidate, report),
        "metrics": _build_metrics(report.metrics, report.gate_reasons, gate_rules),
        "runs": await _build_runs(session, baseline, candidate),
        "traceCases": paginated_trace_cases,
        "tracePagination": {
            "total": len(trace_cases),
            "limit": failure_limit,
            "offset": failure_offset,
            "returned": len(paginated_trace_cases),
        },
        "tagBreakdown": await _build_tag_breakdown(session, baseline, candidate),
        "gateRules": await _build_gate_rules(
            session,
            comparison.gate_rules_id,
            report.gate_reasons,
        ),
    }


async def _load_comparison(
    session: AsyncSession,
    comparison_id: str | None,
    organization_id: str,
) -> Comparison | None:
    if comparison_id is not None:
        return await session.scalar(
            select(Comparison).where(
                Comparison.id == comparison_id,
                Comparison.organization_id == organization_id,
            )
        )

    return await session.scalar(
        select(Comparison)
        .where(
            Comparison.status == "computed",
            Comparison.organization_id == organization_id,
        )
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
    suite = await session.get(EvalSuite, candidate.suite_id)
    app = await session.get(App, candidate_version.app_id) if candidate_version else None
    elapsed_seconds = _elapsed_seconds(baseline, candidate)
    total_executions = baseline.case_completed + candidate.case_completed

    return {
        "generatedAt": report.created_at.isoformat(),
        "benchmark": "latest_persisted_comparison",
        "projectName": app.name if app else "Unknown app",
        "suiteName": suite.name if suite else candidate.suite_id,
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
    gate_rules: dict[str, Any],
) -> list[dict[str, Any]]:
    verdicts_by_metric = {str(reason["metric"]): str(reason["verdict"]) for reason in gate_reasons}
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
            "tolerance": _as_float(gate_rules.get(key, {}).get("tolerance", 0.0)),
            "status": (
                verdicts_by_metric.get(key, "pass") if key in gate_rules else "not_evaluated"
            ),
        }
        for key, label, short_label, unit, direction in METRIC_SPECS
        if key in metrics
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
    suite = await session.get(EvalSuite, run.suite_id)
    samples = await _collect_run_display_samples(session, run.id)
    return {
        "id": run.id,
        "version": version.name if version else run.app_version_id,
        "suite": suite.name if suite else run.suite_id,
        "cases": run.case_count,
        "caseCompleted": run.case_completed,
        "caseErrored": run.case_errored,
        "passRate": _average(samples["case_passes"]),
        "semanticSimilarity": _average(samples["semantic_scores"]),
        "p95LatencyMs": percentile(samples["latencies"], 0.95),
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
    results_by_item = await _load_results_by_item(session, [item.id for item in items])
    for item in items:
        results = results_by_item.get(item.id, [])
        applicable = [
            result
            for result in results
            if not result.skipped and not result.errored and result.passed is not None
        ]
        has_evaluator_error = any(result.errored for result in results)
        samples["case_passes"].append(
            1.0
            if applicable
            and not has_evaluator_error
            and all(result.passed for result in applicable)
            else 0.0
        )
        semantic = _find_first_result(results, ["token_f1_overlap", "semantic_similarity"])
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
    results_by_item = await _load_results_by_item(session, [item.id for item in candidate_items])
    failed_by_item: dict[str, EvalResult | None] = {}
    for item in candidate_items:
        failed = [
            result
            for result in results_by_item.get(item.id, [])
            if (result.passed is False or result.errored) and not result.skipped
        ]
        if failed:
            failed_by_item[item.id] = failed[0]
        elif item.status in {"errored", "timed_out", "cancelled"}:
            failed_by_item[item.id] = None

    failed_items = [item for item in candidate_items if item.id in failed_by_item]
    if not failed_items:
        return []

    cases = list(
        await session.scalars(
            select(EvalCase).where(EvalCase.id.in_([item.case_id for item in failed_items]))
        )
    )
    cases_by_id = {case.id: case for case in cases}
    baseline_item_ids = [
        baseline_by_case[item.case_id].id
        for item in failed_items
        if item.case_id in baseline_by_case
    ]
    traces = list(
        await session.scalars(
            select(Trace).where(
                Trace.run_item_id.in_([item.id for item in failed_items] + baseline_item_ids)
            )
        )
    )
    traces_by_item = {trace.run_item_id: trace for trace in traces}
    candidate_version = await session.get(AppVersion, candidate.app_version_id)
    adapter_module = candidate_version.adapter_module if candidate_version else "unknown"

    trace_cases: list[dict[str, Any]] = []
    for item in failed_items:
        results = results_by_item.get(item.id, [])
        case = cases_by_id.get(item.case_id)
        trace = traces_by_item.get(item.id)
        baseline_item = baseline_by_case.get(item.case_id)
        baseline_trace = traces_by_item.get(baseline_item.id) if baseline_item else None
        if case is None:
            continue

        trace_cases.append(
            _trace_case_to_dashboard_row(
                case=case,
                item=item,
                trace=trace,
                baseline_trace=baseline_trace,
                results=results,
                failed_result=failed_by_item[item.id],
                adapter_module=adapter_module,
            )
        )

    return sorted(trace_cases, key=lambda trace_case: trace_case["id"])


async def _build_tag_breakdown(
    session: AsyncSession,
    baseline: EvalRun,
    candidate: EvalRun,
) -> list[dict[str, Any]]:
    baseline_counts, _baseline_failures = await _run_tag_stats(session, baseline.id)
    candidate_counts, candidate_failures = await _run_tag_stats(session, candidate.id)
    tags = sorted(set(baseline_counts) | set(candidate_counts) | set(candidate_failures))

    breakdown = []
    for tag in tags:
        candidate_count = candidate_counts.get(tag, 0)
        failure_count = candidate_failures.get(tag, 0)
        breakdown.append(
            {
                "tag": tag,
                "baselineCaseCount": baseline_counts.get(tag, 0),
                "candidateCaseCount": candidate_count,
                "candidateFailureCount": failure_count,
                "candidatePassRate": _candidate_pass_rate(candidate_count, failure_count),
            }
        )
    return breakdown


async def _run_tag_stats(
    session: AsyncSession, run_id: str
) -> tuple[dict[str, int], dict[str, int]]:
    counts: dict[str, int] = {}
    failures: dict[str, int] = {}
    items = list(await session.scalars(select(EvalRunItem).where(EvalRunItem.run_id == run_id)))
    cases = list(
        await session.scalars(
            select(EvalCase).where(EvalCase.id.in_([item.case_id for item in items]))
        )
    )
    cases_by_id = {case.id: case for case in cases}
    results_by_item = await _load_results_by_item(session, [item.id for item in items])
    for item in items:
        case = cases_by_id.get(item.case_id)
        if case is None:
            continue
        tag = _first_tag(case.payload)
        counts[tag] = counts.get(tag, 0) + 1
        if any(
            (result.passed is False or result.errored) and not result.skipped
            for result in results_by_item.get(item.id, [])
        ) or item.status in {"errored", "timed_out", "cancelled"}:
            failures[tag] = failures.get(tag, 0) + 1
    return counts, failures


def _candidate_pass_rate(candidate_count: int, failure_count: int) -> float:
    if candidate_count == 0:
        return 0.0
    return round(1 - (failure_count / candidate_count), 6)


async def _load_items_by_case(session: AsyncSession, run_id: str) -> dict[str, EvalRunItem]:
    items = list(await session.scalars(select(EvalRunItem).where(EvalRunItem.run_id == run_id)))
    return {item.case_id: item for item in items}


async def _load_results_by_item(
    session: AsyncSession, run_item_ids: list[str]
) -> dict[str, list[EvalResult]]:
    grouped: dict[str, list[EvalResult]] = {}
    if not run_item_ids:
        return grouped
    results = list(
        await session.scalars(select(EvalResult).where(EvalResult.run_item_id.in_(run_item_ids)))
    )
    for result in results:
        grouped.setdefault(result.run_item_id, []).append(result)
    return grouped


def _trace_case_to_dashboard_row(
    case: EvalCase,
    item: EvalRunItem,
    trace: Trace | None,
    baseline_trace: Trace | None,
    results: list[EvalResult],
    failed_result: EvalResult | None,
    adapter_module: str,
) -> dict[str, Any]:
    semantic = _find_first_result(results, ["token_f1_overlap", "semantic_similarity"])
    keywords = _find_result(results, "contains_keywords")
    retrieval = _find_result(results, "retrieval_hit_rate")
    payload = case.payload

    return {
        "id": case.external_id or case.id,
        "tag": _first_tag(payload),
        "evaluator": failed_result.evaluator_name if failed_result else "execution",
        "reason": _failure_reason(failed_result, item),
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
        "adapter": (
            str(trace.payload.get("metadata", {}).get("adapter_module", adapter_module))
            if trace
            else adapter_module
        ),
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


def _failure_reason(result: EvalResult | None, item: EvalRunItem) -> str:
    if result is not None and result.error_message:
        return result.error_message
    if result is not None:
        return f"{result.evaluator_name} failed"
    return item.error_message or f"Execution {item.status}"


def _trace_answer(trace: Trace | None) -> str:
    if trace is None:
        return ""
    output = trace.payload.get("output", {})
    if isinstance(output, dict):
        return str(output.get("answer", ""))
    return ""


def _trace_chunks(trace: Trace | None) -> list[dict[str, Any]]:
    if trace is None:
        return []
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
                "text": str(chunk.get("text") or chunk.get("chunk_text") or ""),
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
    for key, label, _short_label, _unit, _direction in METRIC_SPECS:
        if key == metric:
            return label
    return metric


def _find_result(results: list[EvalResult], evaluator_name: str) -> EvalResult | None:
    for result in results:
        if result.evaluator_name == evaluator_name:
            return result
    return None


def _find_first_result(
    results: list[EvalResult],
    evaluator_names: list[str],
) -> EvalResult | None:
    for evaluator_name in evaluator_names:
        result = _find_result(results, evaluator_name)
        if result is not None:
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
