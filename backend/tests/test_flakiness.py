import pytest

from app.services.flakiness import classify_flaky_cases, summarize_flakiness


def test_classify_flaky_cases_uses_score_variance_thresholds():
    observations = {
        "stable-case": [0.91, 0.92, 0.90, 0.91, 0.92],
        "flaky-case": [0.9, 0.72, 0.81, 0.66, 0.78],
        "inconclusive-case": [0.95, 0.2, 0.82, 0.11, 0.71],
    }

    classifications = classify_flaky_cases(observations)

    assert classifications["stable-case"].classification == "stable"
    assert classifications["flaky-case"].classification == "flaky"
    assert classifications["inconclusive-case"].classification == "inconclusive"
    assert classifications["stable-case"].score_stddev < 0.05
    assert 0.05 <= classifications["flaky-case"].score_stddev < 0.2
    assert classifications["inconclusive-case"].score_stddev >= 0.2


def test_classify_flaky_cases_rejects_cases_without_repeated_scores():
    with pytest.raises(ValueError, match="at least two scores"):
        classify_flaky_cases({"only-once": [0.9]})


def test_summarize_flakiness_counts_classifications():
    classifications = classify_flaky_cases(
        {
            "stable-a": [0.9, 0.91, 0.9],
            "stable-b": [0.4, 0.41, 0.4],
            "flaky-a": [0.9, 0.72, 0.81],
            "inconclusive-a": [0.99, 0.1, 0.51],
        }
    )

    summary = summarize_flakiness(classifications)

    assert summary.total_cases == 4
    assert summary.stable_count == 2
    assert summary.flaky_count == 1
    assert summary.inconclusive_count == 1
    assert summary.excluded_from_gate == ["flaky-a", "inconclusive-a"]
