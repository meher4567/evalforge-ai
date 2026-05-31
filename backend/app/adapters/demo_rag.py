from __future__ import annotations

from typing import Any

from app.adapters.base import AdapterOutput
from app.evaluators.text import tokenize

DEFAULT_CORPUS = [
    {
        "doc_id": "python-venv",
        "text": "The venv module creates lightweight Python virtual environments.",
        "answer": "Python uses the venv module for virtual environments.",
    },
    {
        "doc_id": "python-json",
        "text": "The json module encodes and decodes JSON documents.",
        "answer": "Python uses the json module for JSON documents.",
    },
    {
        "doc_id": "python-asyncio",
        "text": "The asyncio module supports concurrent code with async and await syntax.",
        "answer": "Python uses asyncio for async concurrency.",
    },
]


def run(question: str, version_config: dict[str, Any]) -> AdapterOutput:
    top_k = int(version_config.get("top_k", 3))
    corpus = version_config.get("corpus", DEFAULT_CORPUS)
    retrieved_chunks = retrieve(question, corpus, top_k=top_k)
    prompt = format_prompt(question, retrieved_chunks)
    answer = generate_answer(version_config, retrieved_chunks)
    latency_ms = int(version_config.get("latency_ms", 100 + 15 * max(top_k, 1)))
    estimated_cost_usd = estimate_cost(prompt, answer, version_config)

    return AdapterOutput(
        answer=answer,
        retrieved_chunks=retrieved_chunks,
        prompt_used=prompt,
        model_used=str(version_config.get("model", "deterministic-demo-rag")),
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        trace_steps=[
            {
                "step": "retrieve",
                "duration_ms": 15,
                "result": {"chunks": retrieved_chunks},
            },
            {
                "step": "format_prompt",
                "duration_ms": 1,
                "result": {"prompt": prompt},
            },
            {
                "step": "generate",
                "duration_ms": max(latency_ms - 16, 1),
                "result": {"answer": answer, "model": version_config.get("model", "demo")},
            },
        ],
    )


def retrieve(question: str, corpus: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    question_tokens = set(tokenize(question))
    scored: list[dict[str, Any]] = []
    for item in corpus:
        text = str(item.get("text", ""))
        text_tokens = set(tokenize(text))
        doc_id = str(item["doc_id"])
        subject_tokens = set(tokenize(doc_id.removeprefix("python-")))
        overlap = len(question_tokens & text_tokens)
        subject_boost = 1.0 if subject_tokens & question_tokens else 0.0
        score = (overlap / max(len(question_tokens), 1)) + subject_boost
        scored.append(
            {
                "doc_id": doc_id,
                "chunk_text": text,
                "score": round(score, 6),
                "answer": str(item.get("answer", "")),
            }
        )

    scored.sort(key=lambda chunk: (-chunk["score"], chunk["doc_id"]))
    return scored[:top_k]


def format_prompt(question: str, retrieved_chunks: list[dict[str, Any]]) -> str:
    context = "\n".join(f"[{chunk['doc_id']}] {chunk['chunk_text']}" for chunk in retrieved_chunks)
    return f"Answer only from the retrieved context.\n\nContext:\n{context}\n\nQuestion: {question}"


def generate_answer(
    version_config: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> str:
    failure_mode = version_config.get("failure_mode")
    if failure_mode == "hallucinate":
        return "Python uses a quantum database to create virtual environments."
    if failure_mode == "refuse":
        return "I do not know."
    if not retrieved_chunks or retrieved_chunks[0]["score"] == 0:
        return "I do not know based on the retrieved context."
    return str(retrieved_chunks[0].get("answer") or retrieved_chunks[0]["chunk_text"])


def estimate_cost(prompt: str, answer: str, version_config: dict[str, Any]) -> float:
    input_rate = float(version_config.get("input_cost_per_1k", 0.0001))
    output_rate = float(version_config.get("output_cost_per_1k", 0.0002))
    input_tokens = len(tokenize(prompt))
    output_tokens = len(tokenize(answer))
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1000, 6)
