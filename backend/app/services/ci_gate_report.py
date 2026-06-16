from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

METRIC_ORDER = ("pass_rate", "semantic_similarity", "p95_latency_ms", "cost_mean_usd")


def should_fail_ci(verdict: str, fail_on_warn: bool = False) -> bool:
    normalized = verdict.lower()
    return normalized == "fail" or (fail_on_warn and normalized == "warn")


def build_ci_gate_report(
    *,
    comparison: Any,
    report: Any,
    dashboard_url: str | None = None,
    fail_on_warn: bool = False,
) -> dict[str, Any]:
    gate_reasons = list(report.gate_reasons or [])
    metrics = _build_metric_rows(report.metrics or {}, gate_reasons)
    payload = {
        "comparison_id": comparison.id,
        "baseline_run_id": comparison.baseline_run_id,
        "candidate_run_id": comparison.candidate_run_id,
        "verdict": report.gate_verdict,
        "should_fail_ci": should_fail_ci(report.gate_verdict, fail_on_warn=fail_on_warn),
        "dashboard_url": dashboard_url,
        "generated_at": datetime.now(UTC).isoformat(),
        "metrics": metrics,
        "gate_reasons": gate_reasons,
    }
    payload["markdown"] = render_markdown_gate_report(payload)
    return payload


def render_markdown_gate_report(payload: dict[str, Any]) -> str:
    lines = [
        "## EvalForge Deployment Gate",
        "",
        f"Gate verdict: `{payload['verdict']}`",
        "",
        "| Metric | Baseline | Candidate | Delta | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in payload["metrics"]:
        lines.append(
            "| {name} | {baseline} | {candidate} | {delta} | {status} |".format(
                name=metric["name"],
                baseline=_format_number(metric["baseline"]),
                candidate=_format_number(metric["candidate"]),
                delta=_format_number(metric["delta"]),
                status=metric["status"],
            )
        )

    if payload["gate_reasons"]:
        lines.extend(["", "### Blocking Reasons"])
        for reason in payload["gate_reasons"]:
            metric = reason.get("metric", "unknown_metric")
            verdict = reason.get("verdict", payload["verdict"])
            delta = reason.get("delta")
            tolerance = reason.get("tolerance")
            detail = f"- `{metric}` returned `{verdict}`"
            if delta is not None and tolerance is not None:
                detail += (
                    f" (delta `{_format_number(delta)}`, tolerance `{_format_number(tolerance)}`)"
                )
            lines.append(detail)

    if payload.get("dashboard_url"):
        lines.extend(["", f"[Open EvalForge dashboard]({payload['dashboard_url']})"])

    return "\n".join(lines) + "\n"


def _build_metric_rows(
    metrics: dict[str, dict[str, Any]],
    gate_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reason_by_metric = {reason.get("metric"): reason for reason in gate_reasons}
    ordered_names = [name for name in METRIC_ORDER if name in metrics]
    ordered_names.extend(sorted(name for name in metrics if name not in METRIC_ORDER))

    rows = []
    for name in ordered_names:
        metric = metrics[name]
        reason = reason_by_metric.get(name)
        rows.append(
            {
                "name": name,
                "baseline": _as_float(metric.get("baseline_point")),
                "candidate": _as_float(metric.get("candidate_point")),
                "delta": _as_float(metric.get("delta_point")),
                "delta_ci": [
                    _as_float(metric.get("delta_ci_lower")),
                    _as_float(metric.get("delta_ci_upper")),
                ],
                "status": reason.get("verdict", "pass") if reason else "pass",
            }
        )
    return rows


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _format_number(value: Any) -> str:
    return f"{float(value):.6f}"
