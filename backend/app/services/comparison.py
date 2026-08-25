from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import new_uuid
from app.models import (
    AppVersion,
    Comparison,
    EvalResult,
    EvalRun,
    EvalRunItem,
    GateRule,
    RegressionReport,
)
from app.services.statistics import average, bootstrap_ci, bootstrap_delta_ci, percentile

DEFAULT_GATE_RULES = {
    "pass_rate": {"direction": "higher_better", "tolerance": 0.02},
    "semantic_similarity": {"direction": "higher_better", "tolerance": 0.02},
    "p95_latency_ms": {"direction": "lower_better", "tolerance": 50.0},
    "cost_mean_usd": {"direction": "lower_better", "tolerance": 0.001},
}

VALID_GATE_DIRECTIONS = {"higher_better", "lower_better"}
MetricSamples = dict[str, dict[str, float]]
MetricSampleInput = Mapping[str, Sequence[float] | Mapping[str, float]]


async def compute_comparison(
    session: AsyncSession,
    baseline_run_id: str,
    candidate_run_id: str,
    gate_rules_id: str | None = None,
    organization_id: str = "00000000-0000-0000-0000-000000000001",
) -> tuple[Comparison, RegressionReport]:
    baseline = await session.scalar(
        select(EvalRun).where(
            EvalRun.id == baseline_run_id,
            EvalRun.organization_id == organization_id,
        )
    )
    candidate = await session.scalar(
        select(EvalRun).where(
            EvalRun.id == candidate_run_id,
            EvalRun.organization_id == organization_id,
        )
    )
    if baseline is None:
        raise ValueError("Baseline run not found")
    if candidate is None:
        raise ValueError("Candidate run not found")
    if baseline.suite_id != candidate.suite_id:
        raise ValueError("Runs must use the same suite")
    if baseline.evaluator_config_id != candidate.evaluator_config_id:
        raise ValueError("Runs must use the same evaluator configuration")

    baseline_version = await session.get(AppVersion, baseline.app_version_id)
    candidate_version = await session.get(AppVersion, candidate.app_version_id)
    if baseline_version is None or candidate_version is None:
        raise ValueError("Run app version not found")
    if baseline_version.app_id != candidate_version.app_id:
        raise ValueError("Runs must belong to the same app")
    if baseline.status not in {"completed", "partial"} or candidate.status not in {
        "completed",
        "partial",
    }:
        raise ValueError("Runs must be completed before comparison")

    baseline_case_ids = set(
        await session.scalars(
            select(EvalRunItem.case_id).where(EvalRunItem.run_id == baseline_run_id)
        )
    )
    candidate_case_ids = set(
        await session.scalars(
            select(EvalRunItem.case_id).where(EvalRunItem.run_id == candidate_run_id)
        )
    )
    if baseline_case_ids != candidate_case_ids:
        raise ValueError("Runs must contain the same evaluation cases")

    gate_rule_id = gate_rules_id or new_uuid()
    if gate_rules_id is None:
        default_rules = GateRule(
            id=gate_rule_id,
            organization_id=organization_id,
            name=f"default-gates-{gate_rule_id[:8]}",
            rules=DEFAULT_GATE_RULES,
        )
        session.add(default_rules)
        gate_rules = DEFAULT_GATE_RULES
    else:
        stored_gate_rules = await session.scalar(
            select(GateRule).where(
                GateRule.id == gate_rules_id,
                GateRule.organization_id == organization_id,
            )
        )
        if stored_gate_rules is None:
            raise ValueError("Gate rules not found")
        gate_rules = validate_gate_rules(stored_gate_rules.rules)

    baseline_metrics = await collect_run_metric_samples(session, baseline_run_id)
    candidate_metrics = await collect_run_metric_samples(session, candidate_run_id)
    metrics = build_metric_report(baseline_metrics, candidate_metrics)
    verdict, reasons = apply_gates(metrics, gate_rules)

    comparison = Comparison(
        organization_id=organization_id,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        gate_rules_id=gate_rule_id,
        status="computed",
    )
    session.add(comparison)
    await session.flush()

    report = RegressionReport(
        comparison_id=comparison.id,
        metrics=metrics,
        gate_verdict=verdict,
        gate_reasons=reasons,
    )
    session.add(report)
    await session.commit()
    await session.refresh(comparison)
    await session.refresh(report)
    return comparison, report


async def collect_run_metric_samples(session: AsyncSession, run_id: str) -> MetricSamples:
    items_result = await session.scalars(
        select(EvalRunItem).where(EvalRunItem.run_id == run_id).order_by(EvalRunItem.case_id.asc())
    )
    items = list(items_result)
    samples: MetricSamples = defaultdict(dict)

    for item in items:
        result_rows = list(
            await session.scalars(select(EvalResult).where(EvalResult.run_item_id == item.id))
        )
        applicable = [
            result
            for result in result_rows
            if not result.skipped and not result.errored and result.passed is not None
        ]
        has_evaluator_error = any(result.errored for result in result_rows)
        samples["pass_rate"][item.case_id] = (
            1.0
            if applicable
            and not has_evaluator_error
            and all(result.passed for result in applicable)
            else 0.0
        )
        if item.recorded_latency_ms is not None:
            samples["p95_latency_ms"][item.case_id] = float(item.recorded_latency_ms)
        if item.recorded_cost_usd is not None:
            samples["cost_mean_usd"][item.case_id] = float(item.recorded_cost_usd)
        for result in result_rows:
            if (
                result.evaluator_name
                in {
                    "semantic_similarity",
                    "token_f1_overlap",
                }
                and result.score is not None
                and not result.errored
                and not result.skipped
            ):
                samples["semantic_similarity"][item.case_id] = float(result.score)

    return dict(samples)


def build_metric_report(
    baseline_samples: MetricSampleInput,
    candidate_samples: MetricSampleInput,
) -> dict[str, Any]:
    statistic_by_metric = {
        "pass_rate": average,
        "semantic_similarity": average,
        "p95_latency_ms": lambda values: percentile(values, 0.95),
        "cost_mean_usd": average,
    }
    report: dict[str, Any] = {}
    for metric, statistic in statistic_by_metric.items():
        baseline_raw = baseline_samples.get(metric, [])
        candidate_raw = candidate_samples.get(metric, [])
        baseline_values = _sample_values(baseline_raw)
        candidate_values = _sample_values(candidate_raw)
        paired_baseline, paired_candidate = _paired_values(baseline_raw, candidate_raw)
        baseline_point = statistic(baseline_values)
        candidate_point = statistic(candidate_values)
        baseline_ci = bootstrap_ci(baseline_values, statistic)
        candidate_ci = bootstrap_ci(candidate_values, statistic)
        delta_ci = bootstrap_delta_ci(paired_baseline, paired_candidate, statistic)
        report[metric] = {
            "baseline_point": round(baseline_point, 6),
            "baseline_ci_lower": round(baseline_ci[0], 6),
            "baseline_ci_upper": round(baseline_ci[1], 6),
            "candidate_point": round(candidate_point, 6),
            "candidate_ci_lower": round(candidate_ci[0], 6),
            "candidate_ci_upper": round(candidate_ci[1], 6),
            "delta_point": round(candidate_point - baseline_point, 6),
            "delta_ci_lower": round(delta_ci[0], 6),
            "delta_ci_upper": round(delta_ci[1], 6),
            "baseline_sample_count": len(baseline_values),
            "candidate_sample_count": len(candidate_values),
            "paired_sample_count": len(paired_baseline),
        }
    return report


def _sample_values(samples: Sequence[float] | Mapping[str, float]) -> list[float]:
    if isinstance(samples, Mapping):
        return [float(samples[key]) for key in sorted(samples)]
    return [float(value) for value in samples]


def _paired_values(
    baseline: Sequence[float] | Mapping[str, float],
    candidate: Sequence[float] | Mapping[str, float],
) -> tuple[list[float], list[float]]:
    if isinstance(baseline, Mapping) and isinstance(candidate, Mapping):
        shared_case_ids = sorted(set(baseline) & set(candidate))
        return (
            [float(baseline[case_id]) for case_id in shared_case_ids],
            [float(candidate[case_id]) for case_id in shared_case_ids],
        )

    baseline_values = _sample_values(baseline)
    candidate_values = _sample_values(candidate)
    paired_count = min(len(baseline_values), len(candidate_values))
    return baseline_values[:paired_count], candidate_values[:paired_count]


def validate_gate_rules(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(rules, dict) or not rules:
        raise ValueError("Gate rules must contain at least one metric")

    validated: dict[str, dict[str, Any]] = {}
    for metric, rule in rules.items():
        if metric not in DEFAULT_GATE_RULES:
            raise ValueError(f"Unsupported gate metric: {metric}")
        if not isinstance(rule, dict):
            raise ValueError(f"Gate rule for {metric} must be an object")
        direction = rule.get("direction")
        if direction not in VALID_GATE_DIRECTIONS:
            raise ValueError(f"Invalid direction for {metric}: {direction}")
        try:
            tolerance = float(rule.get("tolerance"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid tolerance for {metric}") from exc
        if not isfinite(tolerance) or tolerance < 0:
            raise ValueError(f"Tolerance for {metric} must be a finite non-negative number")
        validated[metric] = {"direction": direction, "tolerance": tolerance}
    return validated


def apply_gates(
    metrics: dict[str, Any],
    gate_rules: dict[str, dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    gate_rules = validate_gate_rules(gate_rules)
    verdict = "pass"
    reasons: list[dict[str, Any]] = []

    for metric, rule in gate_rules.items():
        metric_report = metrics[metric]
        direction = rule["direction"]
        tolerance = float(rule["tolerance"])
        delta_lower = float(metric_report["delta_ci_lower"])
        delta_upper = float(metric_report["delta_ci_upper"])
        delta_point = float(metric_report["delta_point"])

        normalized_upper = delta_upper if direction == "higher_better" else -delta_lower
        normalized_lower = delta_lower if direction == "higher_better" else -delta_upper
        normalized_point = delta_point if direction == "higher_better" else -delta_point

        metric_verdict = "pass"
        if normalized_upper < -tolerance:
            metric_verdict = "fail"
        elif normalized_lower < -tolerance or normalized_point < -tolerance:
            metric_verdict = "warn"

        if metric_verdict != "pass":
            reasons.append(
                {
                    "metric": metric,
                    "verdict": metric_verdict,
                    "tolerance": tolerance,
                    "delta_point": delta_point,
                }
            )
        if metric_verdict == "fail":
            verdict = "fail"
        elif metric_verdict == "warn" and verdict != "fail":
            verdict = "warn"

    return verdict, reasons
