from app.adapters.demo_rag import run


def test_demo_rag_adapter_retrieves_relevant_chunk_and_returns_trace():
    output = run(
        "Which Python module creates virtual environments?",
        {
            "top_k": 2,
            "corpus": [
                {
                    "doc_id": "venv",
                    "text": "The venv module creates lightweight virtual environments.",
                    "answer": "Python uses the venv module for virtual environments.",
                },
                {
                    "doc_id": "json",
                    "text": "The json module encodes and decodes JSON documents.",
                    "answer": "Python uses json for JSON documents.",
                },
            ],
        },
    )

    assert output.answer == "Python uses the venv module for virtual environments."
    assert output.retrieved_chunks[0]["doc_id"] == "venv"
    assert output.prompt_used.startswith("Answer only from the retrieved context")
    assert output.model_used == "deterministic-demo-rag"
    assert output.latency_ms > 0
    assert output.estimated_cost_usd >= 0
    assert [step["step"] for step in output.trace_steps] == [
        "retrieve",
        "format_prompt",
        "generate",
    ]


def test_demo_rag_adapter_can_simulate_bad_candidate_output():
    output = run(
        "Which Python module creates virtual environments?",
        {
            "failure_mode": "hallucinate",
            "corpus": [
                {
                    "doc_id": "venv",
                    "text": "The venv module creates lightweight virtual environments.",
                    "answer": "Python uses the venv module for virtual environments.",
                }
            ],
        },
    )

    assert "quantum" in output.answer.lower()
