import pytest

from app.adapters import groq_chat


def test_groq_chat_adapter_calls_groq_and_returns_evalforge_output(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        groq_chat,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "groq_api_key": "test-secret",
                "llm_model": "llama-test-model",
                "llm_base_url": "https://api.groq.com/openai/v1",
            },
        )(),
    )

    def fake_post_chat_completion(base_url, api_key, payload, timeout_seconds):
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "choices": [{"message": {"content": "Python uses the venv module."}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 6},
        }

    monkeypatch.setattr(groq_chat, "_post_chat_completion", fake_post_chat_completion)

    output = groq_chat.run(
        "Which Python module creates virtual environments?",
        {
            "base_url": "https://api.groq.com/openai/v1",
            "model": "llama-test-model",
            "top_k": 1,
            "temperature": 0.0,
            "max_tokens": 64,
            "timeout_seconds": 12,
            "input_cost_per_1k": 0.1,
            "output_cost_per_1k": 0.2,
            "corpus": [
                {
                    "doc_id": "venv",
                    "text": "The venv module creates lightweight Python virtual environments.",
                },
                {
                    "doc_id": "json",
                    "text": "The json module encodes and decodes JSON documents.",
                },
            ],
        },
    )

    assert captured["base_url"] == "https://api.groq.com/openai/v1"
    assert captured["api_key"] == "test-secret"
    assert captured["timeout_seconds"] == 12
    assert captured["payload"]["model"] == "llama-test-model"
    assert captured["payload"]["temperature"] == 0.0
    assert captured["payload"]["max_tokens"] == 64
    assert "venv module" in captured["payload"]["messages"][-1]["content"]

    assert output.answer == "Python uses the venv module."
    assert output.model_used == "llama-test-model"
    assert output.retrieved_chunks[0]["doc_id"] == "venv"
    assert output.estimated_cost_usd == pytest.approx(0.0054)
    assert [step["step"] for step in output.trace_steps] == [
        "retrieve",
        "format_prompt",
        "call_groq",
    ]
    assert "test-secret" not in str(output.trace_steps)


def test_groq_chat_adapter_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(
        groq_chat,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "groq_api_key": None,
                "llm_model": "llama-test-model",
                "llm_base_url": "https://api.groq.com/openai/v1",
            },
        )(),
    )

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        groq_chat.run("hello", {})
