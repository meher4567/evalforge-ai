from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

STABLE_STDDEV_THRESHOLD = 0.05
INCONCLUSIVE_STDDEV_THRESHOLD = 0.20


@dataclass(frozen=True)
class FlakyCaseClassification:
    case_id: str
    run_count: int
    mean_score: float
    score_stddev: float
    classification: str


@dataclass(frozen=True)
class FlakinessSummary:
    total_cases: int
    stable_count: int
    flaky_count: int
    inconclusive_count: int
    excluded_from_gate: list[str]


def classify_flaky_cases(
    observations: dict[str, list[float]],
) -> dict[str, FlakyCaseClassification]:
    classifications: dict[str, FlakyCaseClassification] = {}

    for case_id, scores in observations.items():
        if len(scores) < 2:
            raise ValueError(f"case {case_id} needs at least two scores for flakiness detection")

        score_stddev = pstdev(scores)
        classifications[case_id] = FlakyCaseClassification(
            case_id=case_id,
            run_count=len(scores),
            mean_score=mean(scores),
            score_stddev=score_stddev,
            classification=_classification_for_stddev(score_stddev),
        )

    return classifications


def summarize_flakiness(
    classifications: dict[str, FlakyCaseClassification],
) -> FlakinessSummary:
    stable_count = sum(
        1
        for classification in classifications.values()
        if classification.classification == "stable"
    )
    flaky_count = sum(
        1 for classification in classifications.values() if classification.classification == "flaky"
    )
    inconclusive_count = sum(
        1
        for classification in classifications.values()
        if classification.classification == "inconclusive"
    )
    excluded_from_gate = [
        case_id
        for case_id, classification in classifications.items()
        if classification.classification in {"flaky", "inconclusive"}
    ]

    return FlakinessSummary(
        total_cases=len(classifications),
        stable_count=stable_count,
        flaky_count=flaky_count,
        inconclusive_count=inconclusive_count,
        excluded_from_gate=excluded_from_gate,
    )


def _classification_for_stddev(score_stddev: float) -> str:
    if score_stddev < STABLE_STDDEV_THRESHOLD:
        return "stable"
    if score_stddev < INCONCLUSIVE_STDDEV_THRESHOLD:
        return "flaky"
    return "inconclusive"
