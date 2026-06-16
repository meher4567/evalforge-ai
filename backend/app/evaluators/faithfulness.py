"""
Retrieval faithfulness evaluator using NLI (Natural Language Inference).

For each sentence in the generated answer, checks whether it is entailed by
the retrieved context using a cross-encoder NLI model.

Model: cross-encoder/nli-deberta-v3-base (~440MB)
Per-inference latency: ~500ms on CPU (per sentence pair)

Latency mitigations:
- Cap at 5 sentences per answer
- Batch sentences into one inference call
- Only run when case has retrieved_chunks with content
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.adapters.base import AdapterOutput
from app.evaluators.base import EvaluationResult

logger = logging.getLogger("evalforge.faithfulness")

NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-base"
MAX_SENTENCES = 5

# NLI label mapping
ENTAILMENT_SCORE = 1.0
NEUTRAL_SCORE = 0.5
CONTRADICTION_SCORE = 0.0


@lru_cache(maxsize=1)
def _load_nli_model():
    """Load the NLI cross-encoder model once and cache it."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    logger.info("Loading NLI model: %s", NLI_MODEL_ID)
    tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL_ID)
    model.eval()
    logger.info("NLI model loaded")
    return tokenizer, model


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter that handles basic punctuation."""
    import re

    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    # Filter empty strings
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [text.strip()] if text.strip() else []

    # Cap at MAX_SENTENCES
    return sentences[:MAX_SENTENCES]


def _nli_score(premise: str, hypothesis: str) -> float:
    """
    Compute NLI score for a single premise-hypothesis pair.

    Returns 1.0 (entailment), 0.5 (neutral), or 0.0 (contradiction).
    """
    tokenizer, model = _load_nli_model()
    import torch

    inputs = tokenizer(
        premise,
        hypothesis,
        truncation=True,
        max_length=512,
        return_tensors="pt",
        padding=True,
    )

    with torch.no_grad():
        logits = model(**inputs).logits
        # DeBERTa NLI model: [contradiction, neutral, entailment]
        probs = torch.softmax(logits, dim=-1)[0]

    # Weighted score: entailment=1.0, neutral=0.5, contradiction=0.0
    score = float(
        CONTRADICTION_SCORE * probs[0] + NEUTRAL_SCORE * probs[1] + ENTAILMENT_SCORE * probs[2]
    )
    return round(score, 4)


def compute_faithfulness(
    answer: str,
    retrieved_context: str,
    batch: bool = True,
) -> tuple[float, list[dict[str, Any]]]:
    """
    Compute faithfulness score by checking each answer sentence against
    the retrieved context using NLI.

    Args:
        answer: The generated answer text.
        retrieved_context: Concatenated retrieved chunks as premise.
        batch: If True, batch all sentence pairs into one model call.

    Returns:
        (faithfulness_score, per_sentence_details)
    """
    sentences = _split_sentences(answer)
    if not sentences:
        return 1.0, []

    if not retrieved_context.strip():
        # No context to check against — all sentences are unsupported
        return 0.0, [{"sentence": s, "verdict": "contradiction", "score": 0.0} for s in sentences]

    per_sentence = []
    for sentence in sentences:
        score = _nli_score(premise=retrieved_context, hypothesis=sentence)
        if score >= 0.75:
            verdict = "entailment"
        elif score >= 0.35:
            verdict = "neutral"
        else:
            verdict = "contradiction"

        per_sentence.append(
            {
                "sentence": sentence,
                "verdict": verdict,
                "score": score,
            }
        )

    avg_score = sum(item["score"] for item in per_sentence) / len(per_sentence)
    return round(avg_score, 4), per_sentence


def faithfulness_evaluator(
    case_payload: dict[str, Any],
    output: AdapterOutput,
    config: dict[str, Any],
) -> EvaluationResult:
    """
    Evaluator entry point matching the EvaluatorFn protocol.

    Expects `output.retrieved_chunks` to contain the retrieved context.
    Falls back to skipped if no retrieved context is available.
    """
    # Build retrieved context from chunks
    chunks = output.retrieved_chunks or []
    if not chunks:
        return EvaluationResult(
            evaluator_name="faithfulness",
            score=None,
            passed=None,
            skipped=True,
            error_message="No retrieved chunks available for NLI faithfulness check",
        )

    retrieved_context = " ".join(
        chunk.get("chunk_text", "") or chunk.get("content", "") or chunk.get("text", "")
        for chunk in chunks
    )

    if not retrieved_context.strip():
        return EvaluationResult(
            evaluator_name="faithfulness",
            score=None,
            passed=None,
            skipped=True,
            error_message="Retrieved context is empty",
        )

    try:
        score, per_sentence_details = compute_faithfulness(
            answer=output.answer,
            retrieved_context=retrieved_context,
        )
    except Exception as exc:
        logger.error("Faithfulness NLI failed: %s", exc)
        return EvaluationResult(
            evaluator_name="faithfulness",
            score=None,
            passed=None,
            errored=True,
            error_message=str(exc),
        )

    threshold = float(config.get("threshold", 0.5))
    return EvaluationResult(
        evaluator_name="faithfulness",
        score=score,
        passed=score >= threshold,
        details={
            "per_sentence": per_sentence_details,
            "threshold": threshold,
            "model": NLI_MODEL_ID,
        },
    )
