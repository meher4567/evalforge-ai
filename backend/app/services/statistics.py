from __future__ import annotations

import random
from collections.abc import Callable
from statistics import mean


def average(values: list[float]) -> float:
    return mean(values) if values else 0.0


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile_value
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_ci(
    values: list[float],
    statistic: Callable[[list[float]], float],
    *,
    n_resamples: int = 1000,
    seed: int = 42,
    method: str = "percentile",
) -> tuple[float, float]:
    if len(values) < 3:
        return (0.0, 0.0)

    rng = random.Random(seed)
    estimates = []
    for _ in range(n_resamples):
        sample = [rng.choice(values) for _ in values]
        estimates.append(statistic(sample))
    estimates.sort()
    return (
        estimates[int(0.025 * (n_resamples - 1))],
        estimates[int(0.975 * (n_resamples - 1))],
    )


def bootstrap_delta_ci(
    baseline_values: list[float],
    candidate_values: list[float],
    statistic: Callable[[list[float]], float],
    *,
    n_resamples: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    if not baseline_values or not candidate_values:
        return (0.0, 0.0)

    rng = random.Random(seed)
    count = min(len(baseline_values), len(candidate_values))
    estimates = []
    for _ in range(n_resamples):
        indices = [rng.randrange(count) for _ in range(count)]
        baseline_sample = [baseline_values[index] for index in indices]
        candidate_sample = [candidate_values[index] for index in indices]
        estimates.append(statistic(candidate_sample) - statistic(baseline_sample))
    estimates.sort()
    return (
        estimates[int(0.025 * (n_resamples - 1))],
        estimates[int(0.975 * (n_resamples - 1))],
    )


def is_significant_regression(
    baseline_values: list[float],
    candidate_values: list[float],
    statistic: Callable[[list[float]], float],
    *,
    direction: str,
    tolerance: float = 0.0,
    n_resamples: int = 1000,
    seed: int = 42,
) -> tuple[bool, str]:
    baseline_point = statistic(baseline_values)
    candidate_point = statistic(candidate_values)
    delta_point = candidate_point - baseline_point
    delta_lower, delta_upper = bootstrap_delta_ci(
        baseline_values,
        candidate_values,
        statistic,
        n_resamples=n_resamples,
        seed=seed,
    )

    if direction == "higher_better":
        point_regressed = delta_point < -tolerance
        ci_confirms = delta_upper < -tolerance
    elif direction == "lower_better":
        point_regressed = delta_point > tolerance
        ci_confirms = delta_lower > tolerance
    else:
        raise ValueError("direction must be 'higher_better' or 'lower_better'")

    if ci_confirms:
        return (
            True,
            "Significant regression: "
            f"baseline={baseline_point:.6f}, candidate={candidate_point:.6f}, "
            f"delta={delta_point:.6f}, ci=({delta_lower:.6f}, {delta_upper:.6f})",
        )
    if point_regressed:
        return (
            False,
            "Possible regression: "
            f"baseline={baseline_point:.6f}, candidate={candidate_point:.6f}, "
            f"delta={delta_point:.6f}, ci=({delta_lower:.6f}, {delta_upper:.6f})",
        )
    return (
        False,
        "No significant regression: "
        f"baseline={baseline_point:.6f}, candidate={candidate_point:.6f}, "
        f"delta={delta_point:.6f}, ci=({delta_lower:.6f}, {delta_upper:.6f})",
    )


def per_tag_analysis(
    values_by_tag: dict[str, list[float]],
    statistic: Callable[[list[float]], float],
    *,
    n_resamples: int = 1000,
    seed: int = 42,
) -> dict[str, dict[str, float | int]]:
    report: dict[str, dict[str, float | int]] = {}
    for tag, values in values_by_tag.items():
        if len(values) < 3:
            report[tag] = {"point": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": len(values)}
            continue
        ci_lower, ci_upper = bootstrap_ci(
            values,
            statistic,
            n_resamples=n_resamples,
            seed=seed,
        )
        report[tag] = {
            "point": statistic(values),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n": len(values),
        }
    return report
