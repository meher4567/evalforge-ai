from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec
from typing import Any

from app.adapters.base import AdapterOutput
from app.evaluators import basic, faithfulness
from app.evaluators.base import EvaluationResult

EvaluatorFn = Callable[[dict[str, Any], AdapterOutput, dict[str, Any]], EvaluationResult]

EVALUATOR_REGISTRY: dict[str, EvaluatorFn] = {
    "exact_match": basic.exact_match,
    "contains_keywords": basic.contains_keywords,
    "semantic_similarity": basic.semantic_similarity,
    "token_f1_overlap": basic.token_f1_overlap,
    "embedding_similarity": basic.embedding_similarity,
    "retrieval_hit_rate": basic.retrieval_hit_rate,
    "forbidden_claim": basic.forbidden_claim,
    "latency_threshold": basic.latency_threshold,
    "cost_threshold": basic.cost_threshold,
    "faithfulness": faithfulness.faithfulness_evaluator,
}

EVALUATOR_METADATA: dict[str, dict[str, Any]] = {
    "exact_match": {"category": "quality", "deterministic": True},
    "contains_keywords": {"category": "quality", "deterministic": True},
    "semantic_similarity": {
        "category": "quality",
        "deterministic": True,
        "deprecated": True,
        "alias_for": "token_f1_overlap",
    },
    "token_f1_overlap": {"category": "quality", "deterministic": True},
    "embedding_similarity": {
        "category": "quality",
        "deterministic": True,
        "dependency_group": "ml",
        "required_modules": ["sentence_transformers"],
    },
    "retrieval_hit_rate": {"category": "retrieval", "deterministic": True},
    "forbidden_claim": {"category": "safety", "deterministic": True},
    "latency_threshold": {"category": "performance", "deterministic": True},
    "cost_threshold": {"category": "cost", "deterministic": True},
    "faithfulness": {
        "category": "groundedness",
        "deterministic": True,
        "dependency_group": "ml",
        "required_modules": ["transformers", "torch"],
    },
}


def evaluator_capabilities() -> list[dict[str, Any]]:
    capabilities = []
    for name in sorted(EVALUATOR_REGISTRY):
        metadata = EVALUATOR_METADATA[name]
        required_modules = metadata.get("required_modules", [])
        missing_modules = [module for module in required_modules if find_spec(module) is None]
        capabilities.append(
            {
                "name": name,
                **metadata,
                "available": not missing_modules,
                "missing_modules": missing_modules,
            }
        )
    return capabilities


def validate_evaluator_config(config: dict[str, Any]) -> dict[str, Any]:
    evaluator_specs = config.get("evaluators")
    if not isinstance(evaluator_specs, list) or not evaluator_specs:
        raise ValueError("Evaluator config must contain a non-empty evaluators list")

    capability_by_name = {item["name"]: item for item in evaluator_capabilities()}
    seen: set[str] = set()
    for index, spec in enumerate(evaluator_specs):
        if not isinstance(spec, dict):
            raise ValueError(f"Evaluator at index {index} must be an object")
        name = str(spec.get("name", "")).strip()
        if not name:
            raise ValueError(f"Evaluator at index {index} is missing a name")
        if name not in EVALUATOR_REGISTRY:
            raise ValueError(f"Unknown evaluator: {name}")
        if name in seen:
            raise ValueError(f"Duplicate evaluator: {name}")
        seen.add(name)
        capability = capability_by_name[name]
        if not capability["available"]:
            missing = ", ".join(capability["missing_modules"])
            raise ValueError(
                f"Evaluator {name} is unavailable; install the ml dependency group "
                f"(missing: {missing})"
            )
    return config


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
