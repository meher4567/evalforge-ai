from __future__ import annotations

import json
from typing import Any

import pytest


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_adapter_calls_chat_endpoint_and_returns_model_answer(monkeypatch):
    from app.adapters import llm_rag

    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse({"message": {"content": "Python uses the venv module."}})

    monkeypatch.setattr(llm_rag.urllib.request, "urlopen", fake_urlopen)

    output = llm_rag.run(
        "Which Python module creates virtual environments?",
        {
            "provider": "ollama",
            "base_url": "http://ollama.test",
            "model": "llama3.2:3b",
            "corpus": [
                {
                    "doc_id": "python-venv",
                    "text": "The venv module creates lightweight Python virtual environments.",
                }
            ],
        },
    )

    assert captured["url"] == "http://ollama.test/api/chat"
    assert captured["body"]["model"] == "llama3.2:3b"
    assert captured["body"]["stream"] is False
    assert "retrieved context" in captured["body"]["messages"][0]["content"].lower()
    assert "python-venv" in captured["body"]["messages"][1]["content"]
    assert output.answer == "Python uses the venv module."
    assert output.model_used == "ollama:llama3.2:3b"
    assert output.retrieved_chunks[0]["doc_id"] == "python-venv"
    assert output.retrieved_chunks[0]["text"].startswith("The venv module")
    assert output.latency_ms >= 0
    assert output.trace_steps[-1]["step"] == "llm_generate"


def test_openai_compatible_adapter_sends_authorization_header(monkeypatch):
    from app.adapters import llm_rag

    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {"choices": [{"message": {"content": "Python uses the json module."}}]}
        )

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_rag.urllib.request, "urlopen", fake_urlopen)

    output = llm_rag.run(
        "Which Python module handles JSON documents?",
        {
            "provider": "openai_compatible",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.1-8b-instant",
            "corpus": [
                {
                    "doc_id": "python-json",
                    "text": "The json module encodes and decodes JSON documents.",
                }
            ],
        },
    )

    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "llama-3.1-8b-instant"
    assert output.answer == "Python uses the json module."
    assert output.model_used == "openai_compatible:llama-3.1-8b-instant"


def test_openai_compatible_adapter_requires_configured_api_key(monkeypatch):
    from app.adapters import llm_rag

    monkeypatch.delenv("MISSING_LLM_KEY", raising=False)

    with pytest.raises(RuntimeError, match="MISSING_LLM_KEY"):
        llm_rag.run(
            "Which Python module handles JSON documents?",
            {
                "provider": "openai_compatible",
                "api_key_env": "MISSING_LLM_KEY",
                "model": "llama-3.1-8b-instant",
            },
        )
