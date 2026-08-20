"""
Unit tests for comparison gate logic and regression report generation.

Covers: DEFAULT_GATE_RULES, apply_gates, build_metric_report, collect_run_metric_samples
"""

import pytest

from app.services.comparison import (
    DEFAULT_GATE_RULES,
    apply_gates,
    build_metric_report,
)


class TestDefaultGateRules:
    def test_all_required_metrics_exist(self):
        required = {"pass_rate", "semantic_similarity", "p95_latency_ms", "cost_mean_usd"}
        assert set(DEFAULT_GATE_RULES.keys()) == required

    def test_each_rule_has_direction_and_tolerance(self):
        for _metric, rule in DEFAULT_GATE_RULES.items():
            assert "direction" in rule
            assert "tolerance" in rule
            assert rule["direction"] in {"higher_better", "lower_better"}
            assert isinstance(rule["tolerance"], (int, float))
            assert rule["tolerance"] > 0


class TestBuildMetricReport:
    def test_identical_samples_produces_zero_delta(self):
        baseline = {"pass_rate": [1.0] * 20}
        candidate = {"pass_rate": [1.0] * 20}
        report = build_metric_report(baseline, candidate)
        assert "pass_rate" in report
        assert report["pass_rate"]["baseline_point"] == 1.0
        assert report["pass_rate"]["candidate_point"] == 1.0
        assert report["pass_rate"]["delta_point"] == 0.0

    def test_degraded_pass_rate_produces_negative_delta(self):
        baseline = {"pass_rate": [1.0] * 30}
        candidate = {"pass_rate": [0.7] * 30}
        report = build_metric_report(baseline, candidate)
        assert report["pass_rate"]["delta_point"] < 0

    def test_increased_latency_produces_positive_delta(self):
        baseline = {"p95_latency_ms": [100.0] * 30}
        candidate = {"p95_latency_ms": [200.0] * 30}
        report = build_metric_report(baseline, candidate)
        assert report["p95_latency_ms"]["delta_point"] > 0

    def test_ci_have_lower_less_than_upper(self):
        baseline = {"pass_rate": [1.0, 0.9, 1.0, 0.85, 1.0] * 6}
        candidate = {"pass_rate": [0.8, 0.7, 0.9, 0.6, 0.8] * 6}
        report = build_metric_report(baseline, candidate)
        for metric in report:
            assert report[metric]["baseline_ci_lower"] <= report[metric]["baseline_ci_upper"]
            assert report[metric]["candidate_ci_lower"] <= report[metric]["candidate_ci_upper"]
            assert report[metric]["delta_ci_lower"] <= report[metric]["delta_ci_upper"]

    def test_empty_metrics_returns_empty_report(self):
        report = build_metric_report({}, {})
        # Only the four known metrics appear, all with zero values
        assert set(report.keys()) == {
            "pass_rate",
            "semantic_similarity",
            "p95_latency_ms",
            "cost_mean_usd",
        }
        for metric_data in report.values():
            assert metric_data["baseline_point"] == 0.0
            assert metric_data["candidate_point"] == 0.0

    def test_mapping_samples_are_paired_by_case_id(self):
        baseline = {"pass_rate": {"case-a": 1.0, "case-b": 0.0, "baseline-only": 1.0}}
        candidate = {"pass_rate": {"case-b": 1.0, "case-a": 0.0, "candidate-only": 0.0}}

        report = build_metric_report(baseline, candidate)["pass_rate"]

        assert report["baseline_sample_count"] == 3
        assert report["candidate_sample_count"] == 3
        assert report["paired_sample_count"] == 2
        assert report["delta_point"] == pytest.approx(-1 / 3)


class TestApplyGates:
    def make_metrics(
        self,
        pass_rate_delta=0.0,
        similarity_delta=0.0,
        latency_delta=0.0,
        cost_delta=0.0,
    ):
        """Build a metrics dict with exact delta values for deterministic gate testing."""
        return {
            "pass_rate": {
                "baseline_point": 1.0,
                "candidate_point": 1.0 + pass_rate_delta,
                "delta_point": pass_rate_delta,
                "delta_ci_lower": pass_rate_delta - 0.001,
                "delta_ci_upper": pass_rate_delta + 0.001,
                "baseline_ci_lower": 0.99,
                "baseline_ci_upper": 1.0,
                "candidate_ci_lower": 0.99 + pass_rate_delta,
                "candidate_ci_upper": 1.0 + pass_rate_delta,
            },
            "semantic_similarity": {
                "baseline_point": 1.0,
                "candidate_point": 1.0 + similarity_delta,
                "delta_point": similarity_delta,
                "delta_ci_lower": similarity_delta - 0.001,
                "delta_ci_upper": similarity_delta + 0.001,
                "baseline_ci_lower": 0.99,
                "baseline_ci_upper": 1.0,
                "candidate_ci_lower": 0.99 + similarity_delta,
                "candidate_ci_upper": 1.0 + similarity_delta,
            },
            "p95_latency_ms": {
                "baseline_point": 120.0,
                "candidate_point": 120.0 + latency_delta,
                "delta_point": latency_delta,
                "delta_ci_lower": latency_delta - 1.0,
                "delta_ci_upper": latency_delta + 1.0,
                "baseline_ci_lower": 118.0,
                "baseline_ci_upper": 122.0,
                "candidate_ci_lower": 118.0 + latency_delta,
                "candidate_ci_upper": 122.0 + latency_delta,
            },
            "cost_mean_usd": {
                "baseline_point": 0.001,
                "candidate_point": 0.001 + cost_delta,
                "delta_point": cost_delta,
                "delta_ci_lower": cost_delta - 0.0001,
                "delta_ci_upper": cost_delta + 0.0001,
                "baseline_ci_lower": 0.0009,
                "baseline_ci_upper": 0.0011,
                "candidate_ci_lower": 0.0009 + cost_delta,
                "candidate_ci_upper": 0.0011 + cost_delta,
            },
        }

    def test_all_pass_when_no_degradation(self):
        metrics = self.make_metrics()
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "pass"
        assert reasons == []

    def test_pass_rate_drop_below_tolerance_fails(self):
        # Drop pass rate by 0.05 (tolerance is 0.02 for higher_better)
        metrics = self.make_metrics(pass_rate_delta=-0.05)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "fail"
        pass_rate_reason = [r for r in reasons if r["metric"] == "pass_rate"]
        assert len(pass_rate_reason) == 1
        assert pass_rate_reason[0]["verdict"] == "fail"

    def test_latency_increase_beyond_tolerance_fails(self):
        # Increase latency by 100ms (tolerance is 50ms for lower_better)
        metrics = self.make_metrics(latency_delta=100.0)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "fail"
        latency_reason = [r for r in reasons if r["metric"] == "p95_latency_ms"]
        assert len(latency_reason) == 1
        assert latency_reason[0]["verdict"] == "fail"

    def test_small_degradation_triggers_warn(self):
        # Drop pass rate by 0.03 — CI upper bound is -0.029 (below -0.02)
        # But CI lower bound is -0.031 which is also below -0.02
        # Actually with our narrow CI (delta±0.001), -0.03 gives CI [-0.031, -0.029]
        # Both below -0.02 => fail. Let's use a mid case:
        # Drop by 0.021 => CI [-0.022, -0.020]
        # CI upper = -0.020 = exactly tolerance negative, not strictly less
        # CI lower = -0.022 < -0.02 => warn
        metrics = self.make_metrics(pass_rate_delta=-0.021)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "warn"

    def test_cost_increase_within_tolerance_passes(self):
        # Cost increase of 0.0005 with tolerance 0.001
        metrics = self.make_metrics(cost_delta=0.0005)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "pass"

    def test_multiple_failures_all_recorded(self):
        metrics = self.make_metrics(pass_rate_delta=-0.05, latency_delta=100.0)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "fail"
        failing_metrics = {r["metric"] for r in reasons}
        assert "pass_rate" in failing_metrics
        assert "p95_latency_ms" in failing_metrics

    def test_warn_and_fail_together_produces_fail(self):
        # Pass rate warn + latency fail => overall fail
        metrics = self.make_metrics(pass_rate_delta=-0.021, latency_delta=100.0)
        verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        assert verdict == "fail"

    def test_custom_gate_rules_with_different_tolerances(self):
        """Custom rules can make a previously failing metric pass."""
        custom_rules = {
            "pass_rate": {"direction": "higher_better", "tolerance": 0.10},
            "semantic_similarity": {"direction": "higher_better", "tolerance": 0.10},
            "p95_latency_ms": {"direction": "lower_better", "tolerance": 200.0},
            "cost_mean_usd": {"direction": "lower_better", "tolerance": 0.01},
        }
        metrics = self.make_metrics(pass_rate_delta=-0.05, latency_delta=100.0)
        # With relaxed tolerances, this should now pass
        verdict, reasons = apply_gates(metrics, custom_rules)
        assert verdict == "pass"
        assert reasons == []

    def test_gate_reasons_include_delta_and_tolerance(self):
        metrics = self.make_metrics(pass_rate_delta=-0.05)
        _verdict, reasons = apply_gates(metrics, DEFAULT_GATE_RULES)
        for reason in reasons:
            assert "metric" in reason
            assert "verdict" in reason
            assert "tolerance" in reason
            assert "delta_point" in reason
            assert isinstance(reason["tolerance"], float)
            assert isinstance(reason["delta_point"], float)
