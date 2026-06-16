import os

import pytest

from app.adapters.groq_chat import run
from app.core.config import get_settings


def test_live_groq_adapter_smoke():
    if os.environ.get("EVALFORGE_RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set EVALFORGE_RUN_LIVE_LLM_TESTS=1 to call Groq")
    if not get_settings().groq_api_key:
        pytest.skip("GROQ_API_KEY is required for live Groq smoke testing")

    output = run(
        "Answer in exactly three words: what does JSON handle?",
        {"max_tokens": 16, "temperature": 0.0, "timeout_seconds": 20},
    )

    assert output.answer
    assert output.model_used
    assert output.latency_ms > 0
    assert [step["step"] for step in output.trace_steps] == ["format_prompt", "call_groq"]
