from __future__ import annotations

from typing import Any

from app.adapters.base import AdapterOutput
from app.evaluators.base import EvaluationResult
from app.evaluators.text import normalize_text, token_f1
from app.services.embedding_cache import (
    EMBEDDING_MODEL_ID,
    compute_embedding_sync,
    cosine_similarity,
)


def exact_match(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    expected = case_payload.get("expected_output")
    if expected is None:
        return skipped("exact_match", "missing expected_output")

    score = 1.0 if normalize_text(output.answer) == normalize_text(str(expected)) else 0.0
    return EvaluationResult(
        evaluator_name="exact_match",
        score=score,
        passed=score == 1.0,
        details={"expected": expected},
    )


def contains_keywords(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    facts = case_payload.get("expected_facts") or []
    if not facts:
        return skipped("contains_keywords", "missing expected_facts")

    answer = output.answer.lower()
    facts_hit = [fact for fact in facts if str(fact).lower() in answer]
    facts_missed = [fact for fact in facts if fact not in facts_hit]
    score = len(facts_hit) / len(facts)
    threshold = float(config.get("threshold", 1.0))
    return EvaluationResult(
        evaluator_name="contains_keywords",
        score=score,
        passed=score >= threshold,
        details={"facts_hit": facts_hit, "facts_missed": facts_missed, "threshold": threshold},
    )


def semantic_similarity(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    result = _token_f1_result(
        evaluator_name="semantic_similarity",
        case_payload=case_payload,
        output=output,
        config=config,
    )
    if result.details is not None and not result.skipped:
        result.details["alias_for"] = "token_f1_overlap"
    return result


def token_f1_overlap(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    return _token_f1_result(
        evaluator_name="token_f1_overlap",
        case_payload=case_payload,
        output=output,
        config=config,
    )


def _token_f1_result(
    evaluator_name: str,
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    expected = case_payload.get("expected_output")
    if expected is None:
        return skipped(evaluator_name, "missing expected_output")

    score = token_f1(output.answer, str(expected))
    threshold = float(config.get("threshold", 0.7))
    return EvaluationResult(
        evaluator_name=evaluator_name,
        score=score,
        passed=score >= threshold,
        details={"threshold": threshold, "method": "token_f1"},
    )


def embedding_similarity(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    expected = case_payload.get("expected_output")
    if expected is None:
        return skipped("embedding_similarity", "missing expected_output")

    expected_embedding = compute_embedding_sync(str(expected))
    actual_embedding = compute_embedding_sync(output.answer)
    score = round(cosine_similarity(actual_embedding, expected_embedding), 6)
    threshold = float(config.get("threshold", 0.7))
    return EvaluationResult(
        evaluator_name="embedding_similarity",
        score=score,
        passed=score >= threshold,
        details={
            "threshold": threshold,
            "method": "sentence_transformer_cosine",
            "model": EMBEDDING_MODEL_ID,
        },
    )


def retrieval_hit_rate(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    expected_id = case_payload.get("expected_chunk_id") or case_payload.get("expected_doc_id")
    if expected_id is None:
        return skipped("retrieval_hit_rate", "missing expected_chunk_id or expected_doc_id")

    retrieved_ids = [chunk.get("doc_id") for chunk in output.retrieved_chunks]
    matched = expected_id in retrieved_ids
    return EvaluationResult(
        evaluator_name="retrieval_hit_rate",
        score=1.0 if matched else 0.0,
        passed=matched,
        details={"expected_id": expected_id, "retrieved_ids": retrieved_ids, "matched": matched},
    )


def forbidden_claim(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    claims = case_payload.get("forbidden_claims") or []
    if not claims:
        return skipped("forbidden_claim", "missing forbidden_claims")

    answer = output.answer.lower()
    triggered = [claim for claim in claims if str(claim).lower() in answer]
    passed = not triggered
    return EvaluationResult(
        evaluator_name="forbidden_claim",
        score=1.0 if passed else 0.0,
        passed=passed,
        details={"triggered_claims": triggered},
    )


def latency_threshold(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    threshold = int(config.get("threshold_ms", 2000))
    if output.latency_ms <= threshold:
        score = 1.0
    else:
        score = max(0.0, 1 - ((output.latency_ms - threshold) / threshold))
    return EvaluationResult(
        evaluator_name="latency_threshold",
        score=score,
        passed=output.latency_ms <= threshold,
        details={"latency_ms": output.latency_ms, "threshold_ms": threshold},
    )


def cost_threshold(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    threshold = float(config.get("threshold_usd", 0.01))
    if output.estimated_cost_usd <= threshold:
        score = 1.0
    else:
        score = max(0.0, 1 - ((output.estimated_cost_usd - threshold) / threshold))
    return EvaluationResult(
        evaluator_name="cost_threshold",
        score=score,
        passed=output.estimated_cost_usd <= threshold,
        details={"estimated_cost_usd": output.estimated_cost_usd, "threshold_usd": threshold},
    )


def skipped(evaluator_name: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        evaluator_name=evaluator_name,
        score=None,
        passed=None,
        details={"reason": reason},
        skipped=True,
    )
