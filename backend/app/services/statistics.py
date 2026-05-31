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
) -> tuple[float, float]:
    if not values:
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
