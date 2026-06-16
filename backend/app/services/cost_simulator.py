"""
Cost simulator for EvalForge AI.

Estimates API cost without making paid API calls by:
1. Tokenizing prompts and responses using tiktoken (OpenAI-family) or HF tokenizers.
2. Looking up published per-1K-token rates from config/model_costs.yaml.
3. Computing estimated cost = (in_tokens * in_rate + out_tokens * out_rate) / 1000.

This makes "cost" a measurable evaluator without requiring paid APIs.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("evalforge.cost_simulator")

# Path to model costs config, relative to this file
_COSTS_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "model_costs.yaml"


@lru_cache(maxsize=1)
def _load_cost_config() -> dict[str, Any]:
    """Load model cost configuration from YAML file. Lazy-imports yaml."""
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed, using default cost config")
        return {"models": {}}

    if not _COSTS_CONFIG_PATH.exists():
        logger.warning("Model costs config not found at %s, using defaults", _COSTS_CONFIG_PATH)
        return {"models": {}}
    with open(_COSTS_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {"models": {}}


def _get_model_rates(model_name: str) -> tuple[float, float]:
    """
    Get (input_rate_per_1k, output_rate_per_1k) for the given model.

    Falls back to default rates if model not found in config.
    """
    config = _load_cost_config()
    models = config.get("models", {})

    # Try exact match first
    model_config = models.get(model_name)
    if model_config is None:
        # Try matching by prefix/suffix
        for key, val in models.items():
            if key != "_default" and (model_name in key or key in model_name):
                model_config = val
                break

    if model_config is None:
        model_config = models.get("_default", {"input_per_1k": 0.001, "output_per_1k": 0.002})

    return float(model_config.get("input_per_1k", 0.001)), float(
        model_config.get("output_per_1k", 0.002)
    )


def estimate_cost(
    prompt: str,
    response: str,
    model_name: str = "gpt-3.5-turbo",
) -> tuple[float, int, int]:
    """
    Estimate the cost of an LLM API call.

    Args:
        prompt: The input prompt text.
        response: The generated response text.
        model_name: The model identifier (e.g., 'gpt-4o', 'llama-3.2-3b-ollama').

    Returns:
        (estimated_cost_usd, input_tokens, output_tokens)
    """
    input_tokens = count_tokens(prompt, model_name)
    output_tokens = count_tokens(response, model_name)
    input_rate, output_rate = _get_model_rates(model_name)

    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1000.0
    return round(cost, 8), input_tokens, output_tokens


def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens for the given text using the appropriate tokenizer.

    Uses tiktoken for OpenAI-family models, falls back to character-based
    estimation (chars/4) for unknown models.
    """
    if not text:
        return 0

    try:
        tokenizer = _get_tokenizer(model_name)
        return len(tokenizer.encode(text))
    except Exception:
        # Fallback: rough character-based estimation
        return max(1, len(text) // 4)


@lru_cache(maxsize=8)
def _get_tokenizer(model_name: str):
    """Get the appropriate tokenizer for a model, cached."""
    try:
        import tiktoken

        # Map common model names to tiktoken encodings
        encoding_name = "cl100k_base"  # Default for GPT-3.5/4
        if "gpt-4" in model_name.lower() or "gpt-3" in model_name.lower():
            encoding_name = "cl100k_base"
        elif "davinci" in model_name.lower() or "text-davinci" in model_name.lower():
            encoding_name = "p50k_base"

        return tiktoken.get_encoding(encoding_name)
    except ImportError:
        logger.warning("tiktoken not available, using char-based token estimation")
        raise
