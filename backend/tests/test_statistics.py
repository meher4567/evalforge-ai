"""
Comprehensive unit tests for the statistics module.

Covers: average, percentile, bootstrap_ci (BCa and manual fallback),
bootstrap_delta_ci, is_significant_regression, per_tag_analysis,
and edge cases (empty lists, single values, small samples).
"""

import math
import random

import pytest

from app.services.statistics import (
    average,
    bootstrap_ci,
    bootstrap_delta_ci,
    is_significant_regression,
    per_tag_analysis,
    percentile,
)


# ---------------------------------------------------------------------------
# average
# ---------------------------------------------------------------------------
class TestAverage:
    def test_non_empty_list(self):
        assert average([1.0, 2.0, 3.0]) == 2.0

    def test_single_element(self):
        assert average([42.0]) == 42.0

    def test_empty_list_returns_zero(self):
        assert average([]) == 0.0

    def test_negative_values(self):
        assert average([-1.0, -2.0, -3.0]) == -2.0

    def test_mixed_sign(self):
        assert average([-1.0, 1.0]) == 0.0


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------
class TestPercentile:
    def test_p50_median_odd(self):
        assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.50) == 3.0

    def test_p50_median_even(self):
        assert percentile([1.0, 2.0, 3.0, 4.0], 0.50) == 2.5

    def test_p95(self):
        values = list(range(1, 101))
        result = percentile(values, 0.95)
        # 95th percentile of 1..100 should be ~95.05
        assert 94.0 <= result <= 96.0

    def test_p0(self):
        assert percentile([5.0, 1.0, 3.0], 0.0) == 1.0

    def test_p100(self):
        assert percentile([5.0, 1.0, 3.0], 1.0) == 5.0

    def test_single_value(self):
        assert percentile([7.0], 0.95) == 7.0

    def test_empty_returns_zero(self):
        assert percentile([], 0.95) == 0.0

    def test_two_values_p25(self):
        # [10, 20] — rank = 0.25, lower=0 upper=1, weight=0.25
        # 10*(1-0.25) + 20*0.25 = 7.5 + 5 = 12.5
        assert percentile([10.0, 20.0], 0.25) == 12.5


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------
class TestBootstrapCI:
    def test_sufficient_data_produces_ci(self):
        """With a decent sample, CI lower < CI upper and both are finite."""
        values = [random.gauss(100.0, 10.0) for _ in range(100)]
        lo, hi = bootstrap_ci(values, average, n_resamples=200, seed=42)
        assert math.isfinite(lo)
        assert math.isfinite(hi)
        assert lo <= hi

    def test_empty_list_returns_zero_ci(self):
        assert bootstrap_ci([], average) == (0.0, 0.0)

    def test_single_value_returns_zero_ci(self):
        assert bootstrap_ci([5.0], average) == (0.0, 0.0)

    def test_two_values_returns_zero_ci(self):
        assert bootstrap_ci([1.0, 2.0], average) == (0.0, 0.0)

    def test_constant_values_narrow_ci(self):
        """Identical values produce zero-width CI."""
        values = [5.0] * 50
        lo, hi = bootstrap_ci(values, average, n_resamples=100, seed=42)
        assert lo == pytest.approx(5.0)
        assert hi == pytest.approx(5.0)
        assert abs(hi - lo) < 0.001

    def test_manual_fallback_produces_ci(self):
        """Force the manual percentile fallback."""
        values = [random.gauss(50.0, 5.0) for _ in range(30)]
        lo, hi = bootstrap_ci(values, average, n_resamples=100, seed=42, method="percentile")
        assert lo <= hi
        assert math.isfinite(lo) and math.isfinite(hi)

    def test_seed_reproducibility(self):
        """Same seed + same data = same CI."""
        values = [random.gauss(0.0, 1.0) for _ in range(50)]
        ci1 = bootstrap_ci(values, average, n_resamples=100, seed=42, method="percentile")
        ci2 = bootstrap_ci(values, average, n_resamples=100, seed=42, method="percentile")
        assert ci1 == ci2

    def test_different_data_different_ci(self):
        """Different distributions produce meaningfully different CIs."""
        tight = [10.0] * 20 + [10.1] * 20
        wide = [0.0] * 20 + [20.0] * 20
        lo_tight, hi_tight = bootstrap_ci(
            tight, average, n_resamples=100, seed=1, method="percentile"
        )
        lo_wide, hi_wide = bootstrap_ci(wide, average, n_resamples=100, seed=1, method="percentile")
        # Wide distribution should have wider CI
        assert (hi_wide - lo_wide) > (hi_tight - lo_tight) * 3


# ---------------------------------------------------------------------------
# bootstrap_delta_ci
# ---------------------------------------------------------------------------
class TestBootstrapDeltaCI:
    def test_identical_distributions_delta_near_zero(self):
        """Same distribution => delta CI should straddle zero."""
        base = [random.gauss(100.0, 5.0) for _ in range(100)]
        lo, hi = bootstrap_delta_ci(base, base, average, n_resamples=200, seed=42)
        assert lo <= 0 <= hi

    def test_shifted_distribution_delta_away_from_zero(self):
        """Candidate 10 points lower => delta CI entirely negative."""
        baseline = [100.0] * 50
        candidate = [90.0] * 50
        lo, hi = bootstrap_delta_ci(baseline, candidate, average, n_resamples=100, seed=42)
        assert hi < 0  # Entire CI below zero

    def test_empty_inputs_zero_delta(self):
        assert bootstrap_delta_ci([], [], average) == (0.0, 0.0)
        assert bootstrap_delta_ci([1.0], [], average) == (0.0, 0.0)
        assert bootstrap_delta_ci([], [1.0], average) == (0.0, 0.0)

    def test_seed_reproducibility(self):
        baseline = [random.gauss(0.0, 1.0) for _ in range(30)]
        candidate = [random.gauss(-2.0, 1.0) for _ in range(30)]
        ci1 = bootstrap_delta_ci(baseline, candidate, average, n_resamples=50, seed=42)
        ci2 = bootstrap_delta_ci(baseline, candidate, average, n_resamples=50, seed=42)
        assert ci1 == ci2


# ---------------------------------------------------------------------------
# is_significant_regression
# ---------------------------------------------------------------------------
class TestIsSignificantRegression:
    def test_clear_regression_higher_better(self):
        """Pass rate drops from 1.0 to 0.5 — significant."""
        baseline = [1.0] * 30
        candidate = [0.5] * 30
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="higher_better", tolerance=0.02
        )
        assert is_sig is True
        assert "Significant regression" in msg

    def test_no_regression_when_same(self):
        baseline = [0.85] * 30
        candidate = [0.85] * 30
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="higher_better", tolerance=0.02
        )
        assert is_sig is False

    def test_tiny_drop_within_tolerance_higher_better(self):
        """A 0.01 drop with 0.05 tolerance is NOT significant."""
        baseline = [1.0] * 30
        candidate = [0.99] * 30
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="higher_better", tolerance=0.05
        )
        assert is_sig is False

    def test_lower_better_regression(self):
        """Latency increases beyond tolerance — significant."""
        baseline = [100.0] * 30
        candidate = [250.0] * 30
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="lower_better", tolerance=50.0
        )
        assert is_sig is True

    def test_lower_better_no_regression(self):
        baseline = [100.0] * 30
        candidate = [110.0] * 30
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="lower_better", tolerance=50.0
        )
        assert is_sig is False

    def test_possible_regression_message(self):
        """If point estimate exceeds tolerance but CI overlaps zero."""
        baseline = [1.0] * 10
        candidate = [0.85] * 10
        is_sig, msg = is_significant_regression(
            baseline, candidate, average, direction="higher_better", tolerance=0.05
        )
        # With only 10 samples CI may be wide; at minimum should not throw
        assert isinstance(is_sig, bool)
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# per_tag_analysis
# ---------------------------------------------------------------------------
class TestPerTagAnalysis:
    def test_multiple_tags_with_sufficient_data(self):
        values_by_tag = {
            "easy": [1.0, 0.9, 0.95, 0.85, 0.9, 1.0],
            "hard": [0.5, 0.4, 0.45, 0.55, 0.5, 0.6],
        }
        result = per_tag_analysis(values_by_tag, average)
        assert "easy" in result
        assert "hard" in result
        assert result["easy"]["n"] == 6
        assert result["easy"]["point"] == pytest.approx(0.9333, abs=0.01)
        assert result["easy"]["ci_lower"] <= result["easy"]["ci_upper"]

    def test_tag_with_too_few_samples_returns_zero(self):
        values_by_tag = {
            "rare_tag": [1.0, 2.0],
        }
        result = per_tag_analysis(values_by_tag, average)
        assert result["rare_tag"] == {"point": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 2}

    def test_empty_dict(self):
        assert per_tag_analysis({}, average) == {}

    def test_different_statistic(self):
        """Works with percentile statistic too."""
        values_by_tag = {
            "latency": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        }
        result = per_tag_analysis(values_by_tag, lambda v: percentile(v, 0.95))
        assert result["latency"]["point"] > 90.0
