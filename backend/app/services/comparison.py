from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import new_uuid
from app.models import (
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


async def compute_comparison(
    session: AsyncSession,
    baseline_run_id: str,
    candidate_run_id: str,
    gate_rules_id: str | None = None,
) -> tuple[Comparison, RegressionReport]:
    baseline = await session.get(EvalRun, baseline_run_id)
    candidate = await session.get(EvalRun, candidate_run_id)
    if baseline is None:
        raise ValueError("Baseline run not found")
    if candidate is None:
        raise ValueError("Candidate run not found")
    if baseline.suite_id != candidate.suite_id:
        raise ValueError("Runs must use the same suite")
    if baseline.status not in {"completed", "partial"} or candidate.status not in {
        "completed",
        "partial",
    }:
        raise ValueError("Runs must be completed before comparison")

    gate_rule_id = gate_rules_id or new_uuid()
    if gate_rules_id is None:
        default_rules = GateRule(
            id=gate_rule_id,
            name=f"default-gates-{gate_rule_id[:8]}",
            rules=DEFAULT_GATE_RULES,
        )
        session.add(default_rules)

    baseline_metrics = await collect_run_metric_samples(session, baseline_run_id)
    candidate_metrics = await collect_run_metric_samples(session, candidate_run_id)
    metrics = build_metric_report(baseline_metrics, candidate_metrics)
    verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)

    comparison = Comparison(
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


async def collect_run_metric_samples(session: AsyncSession, run_id: str) -> dict[str, list[float]]:
    items_result = await session.scalars(
        select(EvalRunItem).where(EvalRunItem.run_id == run_id).order_by(EvalRunItem.case_id.asc())
    )
    items = list(items_result)
    samples: dict[str, list[float]] = defaultdict(list)

    for item in items:
        result_rows = list(
            await session.scalars(select(EvalResult).where(EvalResult.run_item_id == item.id))
        )
        applicable = [
            result
            for result in result_rows
            if not result.skipped and not result.errored and result.passed is not None
        ]
        samples["pass_rate"].append(
            1.0 if applicable and all(result.passed for result in applicable) else 0.0
        )
        if item.recorded_latency_ms is not None:
            samples["p95_latency_ms"].append(float(item.recorded_latency_ms))
        if item.recorded_cost_usd is not None:
            samples["cost_mean_usd"].append(float(item.recorded_cost_usd))
        for result in result_rows:
            if (
                result.evaluator_name
                in {
                    "semantic_similarity",
                    "token_f1_overlap",
                }
                and result.score is not None
            ):
                samples["semantic_similarity"].append(float(result.score))

    return dict(samples)


def build_metric_report(
    baseline_samples: dict[str, list[float]],
    candidate_samples: dict[str, list[float]],
) -> dict[str, Any]:
    statistic_by_metric = {
        "pass_rate": average,
        "semantic_similarity": average,
        "p95_latency_ms": lambda values: percentile(values, 0.95),
        "cost_mean_usd": average,
    }
    report: dict[str, Any] = {}
    for metric, statistic in statistic_by_metric.items():
        baseline_values = baseline_samples.get(metric, [])
        candidate_values = candidate_samples.get(metric, [])
        baseline_point = statistic(baseline_values)
        candidate_point = statistic(candidate_values)
        baseline_ci = bootstrap_ci(baseline_values, statistic)
        candidate_ci = bootstrap_ci(candidate_values, statistic)
        delta_ci = bootstrap_delta_ci(baseline_values, candidate_values, statistic)
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
        }
    return report


def apply_gates(
    metrics: dict[str, Any],
    gate_rules: dict[str, dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
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
