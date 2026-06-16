from types import SimpleNamespace

from app.services.ci_gate_report import build_ci_gate_report, should_fail_ci


def _sample_metrics() -> dict:
    return {
        "pass_rate": {
            "baseline_point": 1.0,
            "candidate_point": 0.82,
            "delta_point": -0.18,
            "delta_ci_lower": -0.22,
            "delta_ci_upper": -0.11,
        },
        "semantic_similarity": {
            "baseline_point": 0.94,
            "candidate_point": 0.89,
            "delta_point": -0.05,
            "delta_ci_lower": -0.08,
            "delta_ci_upper": -0.02,
        },
        "p95_latency_ms": {
            "baseline_point": 120.0,
            "candidate_point": 180.0,
            "delta_point": 60.0,
            "delta_ci_lower": 40.0,
            "delta_ci_upper": 82.0,
        },
    }


def test_build_ci_gate_report_marks_failed_verdict_as_ci_failure():
    comparison = SimpleNamespace(
        id="cmp-123",
        baseline_run_id="run-base",
        candidate_run_id="run-candidate",
    )
    report = SimpleNamespace(
        gate_verdict="fail",
        gate_reasons=[
            {
                "metric": "pass_rate",
                "verdict": "fail",
                "delta": -0.18,
                "tolerance": -0.02,
            }
        ],
        metrics=_sample_metrics(),
    )

    payload = build_ci_gate_report(
        comparison=comparison,
        report=report,
        dashboard_url="http://localhost:5173/comparisons/cmp-123",
    )

    assert payload["comparison_id"] == "cmp-123"
    assert payload["verdict"] == "fail"
    assert payload["should_fail_ci"] is True
    assert payload["dashboard_url"] == "http://localhost:5173/comparisons/cmp-123"
    assert payload["metrics"][0]["name"] == "pass_rate"
    assert payload["metrics"][0]["status"] == "fail"
    assert payload["metrics"][0]["delta_ci"] == [-0.22, -0.11]
    assert "EvalForge Deployment Gate" in payload["markdown"]
    assert "| pass_rate | 1.000000 | 0.820000 | -0.180000 | fail |" in payload["markdown"]
    assert "http://localhost:5173/comparisons/cmp-123" in payload["markdown"]


def test_build_ci_gate_report_keeps_warn_non_blocking_by_default():
    comparison = SimpleNamespace(
        id="cmp-456",
        baseline_run_id="run-base",
        candidate_run_id="run-candidate",
    )
    report = SimpleNamespace(
        gate_verdict="warn",
        gate_reasons=[{"metric": "p95_latency_ms", "verdict": "warn"}],
        metrics=_sample_metrics(),
    )

    payload = build_ci_gate_report(comparison=comparison, report=report)

    assert payload["verdict"] == "warn"
    assert payload["should_fail_ci"] is False
    assert payload["metrics"][2]["status"] == "warn"
    assert "Gate verdict: `warn`" in payload["markdown"]


def test_should_fail_ci_can_treat_warn_as_blocking():
    assert should_fail_ci("pass") is False
    assert should_fail_ci("warn") is False
    assert should_fail_ci("warn", fail_on_warn=True) is True
    assert should_fail_ci("fail") is True
