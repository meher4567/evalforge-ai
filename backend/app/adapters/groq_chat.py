from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.adapters.base import AdapterOutput
from app.adapters.demo_rag import format_prompt, retrieve
from app.core.config import get_settings


def run(question: str, version_config: dict[str, Any]) -> AdapterOutput:
    settings = get_settings()
    api_key = str(version_config.get("api_key") or settings.groq_api_key or "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is required for app.adapters.groq_chat")

    model = str(version_config.get("model") or settings.llm_model)
    base_url = str(version_config.get("base_url") or settings.llm_base_url)
    timeout_seconds = float(version_config.get("timeout_seconds", 30))

    trace_steps: list[dict[str, Any]] = []
    retrieved_chunks = _retrieve_if_configured(question, version_config, trace_steps)
    prompt = _format_user_prompt(question, retrieved_chunks, version_config, trace_steps)
    payload = _build_payload(prompt, model, version_config)

    started = time.perf_counter()
    response = _post_chat_completion(base_url, api_key, payload, timeout_seconds)
    latency_ms = max(1, int((time.perf_counter() - started) * 1000))

    answer = _extract_answer(response)
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    estimated_cost = _estimate_cost(usage, version_config)
    trace_steps.append(
        {
            "step": "call_groq",
            "duration_ms": latency_ms,
            "result": {
                "base_url": base_url.rstrip("/"),
                "model": model,
                "usage": usage,
                "finish_reason": _extract_finish_reason(response),
            },
        }
    )

    return AdapterOutput(
        answer=answer,
        retrieved_chunks=retrieved_chunks,
        prompt_used=prompt,
        model_used=model,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost,
        trace_steps=trace_steps,
    )


def _retrieve_if_configured(
    question: str,
    version_config: dict[str, Any],
    trace_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    corpus = version_config.get("corpus")
    if not corpus:
        return []

    started = time.perf_counter()
    top_k = int(version_config.get("top_k", 3))
    retrieved_chunks = retrieve(question, list(corpus), top_k=top_k)
    trace_steps.append(
        {
            "step": "retrieve",
            "duration_ms": max(1, int((time.perf_counter() - started) * 1000)),
            "result": {"chunks": retrieved_chunks},
        }
    )
    return retrieved_chunks


def _format_user_prompt(
    question: str,
    retrieved_chunks: list[dict[str, Any]],
    version_config: dict[str, Any],
    trace_steps: list[dict[str, Any]],
) -> str:
    started = time.perf_counter()
    if retrieved_chunks:
        prompt = format_prompt(question, retrieved_chunks)
    else:
        prompt_template = str(version_config.get("prompt_template", "{question}"))
        prompt = prompt_template.format(question=question)

    trace_steps.append(
        {
            "step": "format_prompt",
            "duration_ms": max(1, int((time.perf_counter() - started) * 1000)),
            "result": {"prompt": prompt},
        }
    )
    return prompt


def _build_payload(
    prompt: str,
    model: str,
    version_config: dict[str, Any],
) -> dict[str, Any]:
    system_prompt = str(
        version_config.get(
            "system_prompt",
            "You are a concise assistant. Answer only with information supported by the prompt.",
        )
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(version_config.get("temperature", 0.0)),
    }
    if "max_tokens" in version_config:
        payload["max_tokens"] = int(version_config["max_tokens"])
    return payload


def _post_chat_completion(
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    try:
        response = httpx.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "EvalForge-AI/0.1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        raise RuntimeError(
            f"Groq API request failed with HTTP {exc.response.status_code}: {body[:500]}"
        ) from exc
    except (httpx.RequestError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Groq API request failed: {exc}") from exc


def _extract_answer(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Groq API response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Groq API response choice was malformed")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Groq API response choice did not include a message")
    content = message.get("content")
    if content is None:
        raise RuntimeError("Groq API response message did not include content")
    return str(content).strip()


def _extract_finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    finish_reason = choices[0].get("finish_reason")
    return str(finish_reason) if finish_reason is not None else None


def _estimate_cost(usage: dict[str, Any], version_config: dict[str, Any]) -> float:
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    input_rate = float(version_config.get("input_cost_per_1k", 0.0))
    output_rate = float(version_config.get("output_cost_per_1k", 0.0))
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1000, 6)
