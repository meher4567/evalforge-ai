from __future__ import annotations

from math import sqrt


def pearson_correlation(evaluator_scores: list[float], gold_labels: list[int]) -> float:
    if len(evaluator_scores) != len(gold_labels) or len(evaluator_scores) < 2:
        return 0.0

    x_values = evaluator_scores
    y_values = [normalize_gold_label(label) for label in gold_labels]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=True))
    x_denominator = sqrt(sum((x - x_mean) ** 2 for x in x_values))
    y_denominator = sqrt(sum((y - y_mean) ** 2 for y in y_values))
    if x_denominator == 0 or y_denominator == 0:
        return 0.0
    return round(numerator / (x_denominator * y_denominator), 6)


def spearman_correlation(evaluator_scores: list[float], gold_labels: list[int]) -> float:
    if len(evaluator_scores) != len(gold_labels) or len(evaluator_scores) < 2:
        return 0.0
    return pearson_correlation(
        rank(evaluator_scores), rank([float(label) for label in gold_labels])
    )


def rank(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position
        while end + 1 < len(ordered) and ordered[end + 1][0] == ordered[position][0]:
            end += 1
        average_rank = (position + end + 2) / 2
        for _value, original_index in ordered[position : end + 1]:
            ranks[original_index] = average_rank
        position = end + 1
    return ranks


def confusion_matrix(
    evaluator_scores: list[float],
    gold_labels: list[int],
) -> dict[str, dict[str, int]]:
    labels = ["pass", "borderline", "fail"]
    matrix = {row: {column: 0 for column in labels} for row in labels}
    for score, label in zip(evaluator_scores, gold_labels, strict=True):
        matrix[bin_evaluator_score(score)][bin_gold_label(label)] += 1
    return matrix


def normalize_gold_label(label: int) -> float:
    return (label - 1) / 4


def bin_evaluator_score(score: float) -> str:
    if score >= 0.7:
        return "pass"
    if score >= 0.5:
        return "borderline"
    return "fail"


def bin_gold_label(label: int) -> str:
    if label >= 4:
        return "pass"
    if label == 3:
        return "borderline"
    return "fail"
