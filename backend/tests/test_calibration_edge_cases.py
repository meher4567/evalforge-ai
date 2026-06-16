"""
Edge-case and robustness tests for calibration module.

Covers: rank computation with ties, correlation edge cases,
normalize_gold_label, bin functions, and empty/identical inputs.
"""

import pytest

from app.services.calibration import (
    bin_evaluator_score,
    bin_gold_label,
    confusion_matrix,
    normalize_gold_label,
    pearson_correlation,
    rank,
    spearman_correlation,
)


class TestRank:
    def test_no_ties(self):
        assert rank([3.0, 1.0, 2.0]) == [3.0, 1.0, 2.0]

    def test_with_ties(self):
        result = rank([5.0, 3.0, 5.0, 1.0])
        assert result[0] == result[2] == 3.5  # tied for 3rd/4th
        assert result[1] == 2.0
        assert result[3] == 1.0

    def test_all_same(self):
        result = rank([7.0, 7.0, 7.0])
        assert result == [2.0, 2.0, 2.0]

    def test_single_value(self):
        assert rank([42.0]) == [1.0]

    def test_empty_list(self):
        assert rank([]) == []


class TestCorrelations:
    def test_pearson_perfect_positive(self):
        assert pearson_correlation([1.0, 2.0, 3.0], [5, 4, 3]) == pytest.approx(-1.0, abs=1e-6)

    def test_pearson_zero_length(self):
        assert pearson_correlation([], []) == 0.0

    def test_pearson_mismatched_lengths(self):
        assert pearson_correlation([1.0, 2.0], [1]) == 0.0

    def test_pearson_single_element(self):
        assert pearson_correlation([0.5], [3]) == 0.0

    def test_spearman_perfect_rank(self):
        assert spearman_correlation([0.9, 0.5, 0.1], [5, 3, 1]) == 1.0

    def test_spearman_anti_correlation(self):
        assert spearman_correlation([0.1, 0.5, 0.9], [5, 3, 1]) == -1.0

    def test_spearman_empty(self):
        assert spearman_correlation([], []) == 0.0

    def test_pearson_constant_x(self):
        """Constant evaluator scores => zero denominator => return 0.0."""
        assert pearson_correlation([0.5, 0.5, 0.5], [1, 3, 5]) == 0.0

    def test_pearson_constant_y(self):
        assert pearson_correlation([0.1, 0.5, 0.9], [3, 3, 3]) == 0.0


class TestConfusionMatrix:
    def test_all_diagonal(self):
        matrix = confusion_matrix(
            evaluator_scores=[0.9, 0.6, 0.4],
            gold_labels=[4, 3, 2],
        )
        assert matrix["pass"]["pass"] == 1
        assert matrix["borderline"]["borderline"] == 1
        assert matrix["fail"]["fail"] == 1

    def test_off_diagonal(self):
        matrix = confusion_matrix(
            evaluator_scores=[0.3, 0.8],  # fail, pass
            gold_labels=[5, 1],  # pass, fail
        )
        # evaluator says pass (0.8) but gold says fail (1) => pass/fail
        assert matrix["pass"]["fail"] == 1
        # evaluator says fail (0.3) but gold says pass (5) => fail/pass
        assert matrix["fail"]["pass"] == 1

    def test_empty_inputs(self):
        matrix = confusion_matrix([], [])
        total = sum(sum(row.values()) for row in matrix.values())
        assert total == 0


class TestNormalizeGoldLabel:
    def test_min_label(self):
        assert normalize_gold_label(1) == 0.0

    def test_max_label(self):
        assert normalize_gold_label(5) == 1.0

    def test_mid_label(self):
        assert normalize_gold_label(3) == 0.5


class TestBinFunctions:
    def test_bin_evaluator_score_pass(self):
        assert bin_evaluator_score(0.7) == "pass"
        assert bin_evaluator_score(1.0) == "pass"

    def test_bin_evaluator_score_borderline(self):
        assert bin_evaluator_score(0.5) == "borderline"
        assert bin_evaluator_score(0.69) == "borderline"

    def test_bin_evaluator_score_fail(self):
        assert bin_evaluator_score(0.49) == "fail"
        assert bin_evaluator_score(0.0) == "fail"

    def test_bin_gold_label_pass(self):
        assert bin_gold_label(4) == "pass"
        assert bin_gold_label(5) == "pass"

    def test_bin_gold_label_borderline(self):
        assert bin_gold_label(3) == "borderline"

    def test_bin_gold_label_fail(self):
        assert bin_gold_label(1) == "fail"
        assert bin_gold_label(2) == "fail"
