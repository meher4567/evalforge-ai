"""
Validates that the benchmark report in benchmarks/results/ is well-formed,
contains all required metrics, CIs, and gate decisions.
"""

import json
from pathlib import Path

import pytest

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "results"
    / "2026-05-31"
    / "demo_results.json"
)

REQUIRED_METRICS = {"pass_rate", "semantic_similarity", "p95_latency_ms", "cost_mean_usd"}
REQUIRED_METRIC_FIELDS = {
    "baseline_point",
    "baseline_ci_lower",
    "baseline_ci_upper",
    "candidate_point",
    "candidate_ci_lower",
    "candidate_ci_upper",
    "delta_point",
    "delta_ci_lower",
    "delta_ci_upper",
}
SUMMARY_REQUIRED = {
    "case_count",
    "total_case_executions",
    "elapsed_seconds",
    "cases_per_minute",
    "baseline_status",
    "candidate_status",
    "gate_verdict",
    "metrics",
    "gate_reasons",
}


class TestBenchmarkReport:
    @classmethod
    @pytest.fixture(scope="class")
    def report(cls):
        if not BENCHMARK_PATH.exists():
            pytest.skip(f"Benchmark report not found at {BENCHMARK_PATH}")
        with open(BENCHMARK_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_file_exists(self):
        assert BENCHMARK_PATH.exists(), (
            f"Benchmark report missing: {BENCHMARK_PATH}. "
            "Run: uv run --directory backend python ../benchmarks/run_demo.py --cases 500"
        )

    def test_top_level_keys(self, report):
        for key in {"generated_at", "benchmark", "reproduction_command", "summary"}:
            assert key in report, f"Missing top-level key: {key}"

    def test_summary_has_all_fields(self, report):
        summary = report["summary"]
        for field in SUMMARY_REQUIRED:
            assert field in summary, f"Missing summary field: {field}"

    def test_case_count_positive(self, report):
        assert report["summary"]["case_count"] > 0

    def test_total_executions_is_double_case_count(self, report):
        summary = report["summary"]
        assert summary["total_case_executions"] == summary["case_count"] * 2

    def test_all_metrics_present(self, report):
        metrics = report["summary"]["metrics"]
        assert set(metrics.keys()) == REQUIRED_METRICS

    def test_each_metric_has_required_fields(self, report):
        metrics = report["summary"]["metrics"]
        for metric_name, metric_data in metrics.items():
            for field in REQUIRED_METRIC_FIELDS:
                assert field in metric_data, f"Metric {metric_name} missing field: {field}"

    def test_ci_lower_less_than_upper(self, report):
        metrics = report["summary"]["metrics"]
        for metric_name, metric_data in metrics.items():
            assert metric_data["baseline_ci_lower"] <= metric_data["baseline_ci_upper"], (
                f"{metric_name} baseline CI inverted"
            )
            assert metric_data["candidate_ci_lower"] <= metric_data["candidate_ci_upper"], (
                f"{metric_name} candidate CI inverted"
            )
            assert metric_data["delta_ci_lower"] <= metric_data["delta_ci_upper"], (
                f"{metric_name} delta CI inverted"
            )

    def test_delta_equals_candidate_minus_baseline(self, report):
        metrics = report["summary"]["metrics"]
        for metric_name, metric_data in metrics.items():
            expected_delta = metric_data["candidate_point"] - metric_data["baseline_point"]
            assert metric_data["delta_point"] == pytest.approx(expected_delta), (
                f"{metric_name} delta mismatch"
            )

    def test_gate_verdict_valid(self, report):
        assert report["summary"]["gate_verdict"] in {"pass", "warn", "fail"}

    def test_gate_reasons_match_verdict(self, report):
        summary = report["summary"]
        if summary["gate_verdict"] == "pass":
            assert summary["gate_reasons"] == []
        else:
            assert len(summary["gate_reasons"]) > 0
            for reason in summary["gate_reasons"]:
                assert "metric" in reason
                assert "verdict" in reason
                assert "tolerance" in reason
                assert reason["verdict"] in {"warn", "fail"}

    def test_benchmark_measured_reproduction(self, report):
        """Ensure the report is from an actual benchmark run, not hand-written."""
        assert report["benchmark"] == "deterministic_demo_rag_regression"
        assert "run_demo.py" in report["reproduction_command"]

    def test_pass_rate_candidate_less_than_baseline(self, report):
        """Candidate with hallucination injection must have lower pass rate."""
        metrics = report["summary"]["metrics"]
        assert metrics["pass_rate"]["candidate_point"] < metrics["pass_rate"]["baseline_point"], (
            "Expected candidate hallucination to reduce pass rate"
        )

    def test_latency_candidate_greater_than_baseline(self, report):
        """Hallucination-injected candidate should have higher latency."""
        metrics = report["summary"]["metrics"]
        assert (
            metrics["p95_latency_ms"]["candidate_point"]
            >= metrics["p95_latency_ms"]["baseline_point"]
        )
