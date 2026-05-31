from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.adapters.base import AdapterOutput
from app.evaluators import basic
from app.evaluators.base import EvaluationResult

EvaluatorFn = Callable[[dict[str, Any], AdapterOutput, dict[str, Any]], EvaluationResult]

EVALUATOR_REGISTRY: dict[str, EvaluatorFn] = {
    "exact_match": basic.exact_match,
    "contains_keywords": basic.contains_keywords,
    "semantic_similarity": basic.semantic_similarity,
    "retrieval_hit_rate": basic.retrieval_hit_rate,
    "forbidden_claim": basic.forbidden_claim,
    "latency_threshold": basic.latency_threshold,
    "cost_threshold": basic.cost_threshold,
}


def evaluate_case(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    evaluator_config: dict[str, Any],
) -> list[EvaluationResult]:
    evaluator_specs = evaluator_config.get("evaluators", [])
    results: list[EvaluationResult] = []

    for spec in evaluator_specs:
        name = str(spec.get("name", ""))
        evaluator = EVALUATOR_REGISTRY.get(name)
        if evaluator is None:
            results.append(
                EvaluationResult(
                    evaluator_name=name or "unknown",
                    score=None,
                    passed=None,
                    errored=True,
                    error_message=f"Unknown evaluator: {name}",
                )
            )
            continue

        try:
            results.append(evaluator(case_payload, output, spec))
        except Exception as exc:
            results.append(
                EvaluationResult(
                    evaluator_name=name,
                    score=None,
                    passed=None,
                    errored=True,
                    error_message=str(exc),
                )
            )

    return results
