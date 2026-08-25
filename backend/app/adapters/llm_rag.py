from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from app.adapters.base import AdapterOutput
from app.adapters.demo_rag import DEFAULT_CORPUS, format_prompt, retrieve
from app.adapters.security import validate_api_key_environment, validate_provider_url
from app.evaluators.text import tokenize

SYSTEM_PROMPT = (
    "You are evaluating a RAG application. Answer only from the retrieved context. "
    "If the context does not contain the answer, say you do not know."
)


def run(question: str, version_config: dict[str, Any]) -> AdapterOutput:
    provider = str(version_config.get("provider", "ollama"))
    model = str(version_config.get("model", _default_model(provider)))
    timeout_seconds = float(version_config.get("timeout_seconds", 30))
    top_k = int(version_config.get("top_k", 3))
    corpus = version_config.get("corpus", DEFAULT_CORPUS)

    started = time.perf_counter()
    retrieved_chunks = _normalize_chunks(retrieve(question, corpus, top_k=top_k))
    prompt = format_prompt(question, retrieved_chunks)

    if provider == "ollama":
        answer = _call_ollama(version_config, model, prompt, timeout_seconds)
    elif provider == "openai_compatible":
        answer = _call_openai_compatible(version_config, model, prompt, timeout_seconds)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    latency_ms = int((time.perf_counter() - started) * 1000)
    estimated_cost_usd = _estimate_cost(prompt, answer, version_config)

    return AdapterOutput(
        answer=answer,
        retrieved_chunks=retrieved_chunks,
        prompt_used=prompt,
        model_used=f"{provider}:{model}",
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        trace_steps=[
            {
                "step": "retrieve",
                "duration_ms": 0,
                "result": {"chunks": retrieved_chunks},
            },
            {
                "step": "format_prompt",
                "duration_ms": 0,
                "result": {"prompt": prompt},
            },
            {
                "step": "llm_generate",
                "duration_ms": latency_ms,
                "result": {"answer": answer, "provider": provider, "model": model},
            },
        ],
    )


def _call_ollama(
    version_config: dict[str, Any],
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    base_url = validate_provider_url(
        str(version_config.get("base_url", "http://localhost:11434")),
        allow_local=True,
    )
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    data = _post_json(f"{base_url}/api/chat", payload, timeout_seconds)
    message = data.get("message", {})
    if not isinstance(message, dict) or not message.get("content"):
        raise RuntimeError("Ollama response did not include message.content")
    return str(message["content"]).strip()


def _call_openai_compatible(
    version_config: dict[str, Any],
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    base_url = validate_provider_url(
        str(version_config.get("base_url", "https://api.openai.com/v1"))
    )
    api_key_env = validate_api_key_environment(
        str(version_config.get("api_key_env", "OPENAI_API_KEY"))
    )
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key environment variable: {api_key_env}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(version_config.get("temperature", 0)),
    }
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        timeout_seconds,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI-compatible response did not include choices")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    if not isinstance(message, dict) or not message.get("content"):
        raise RuntimeError("OpenAI-compatible response did not include message.content")
    return str(message["content"]).strip()


def _post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM provider request failed: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("LLM provider response was not a JSON object")
    return data


def _normalize_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for chunk in chunks:
        text = str(chunk.get("text") or chunk.get("chunk_text") or "")
        normalized.append(
            {
                **chunk,
                "text": text,
                "chunk_text": text,
            }
        )
    return normalized


def _estimate_cost(prompt: str, answer: str, version_config: dict[str, Any]) -> float:
    input_rate = float(version_config.get("input_cost_per_1k", 0))
    output_rate = float(version_config.get("output_cost_per_1k", 0))
    input_tokens = len(tokenize(prompt))
    output_tokens = len(tokenize(answer))
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1000, 6)


def _default_model(provider: str) -> str:
    if provider == "openai_compatible":
        return "gpt-4o-mini"
    return "llama3.2:3b"
