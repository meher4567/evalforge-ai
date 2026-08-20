from app.adapters.base import AdapterOutput
from app.evaluators import faithfulness


def test_compute_faithfulness_batches_sentences(monkeypatch):
    calls = []

    def fake_scores(premise: str, hypotheses: list[str]) -> list[float]:
        calls.append((premise, hypotheses))
        return [1.0, 0.5]

    monkeypatch.setattr(faithfulness, "_nli_scores", fake_scores)

    score, details = faithfulness.compute_faithfulness(
        "The first claim is supported. The second claim is uncertain.",
        "retrieved evidence",
    )

    assert score == 0.75
    assert len(calls) == 1
    assert calls[0][1] == [
        "The first claim is supported.",
        "The second claim is uncertain.",
    ]
    assert [detail["verdict"] for detail in details] == ["entailment", "neutral"]


def test_faithfulness_evaluator_skips_missing_context():
    output = AdapterOutput(
        answer="An answer",
        retrieved_chunks=[],
        prompt_used="prompt",
        model_used="model",
        latency_ms=1,
        estimated_cost_usd=0.0,
        trace_steps=[],
    )

    result = faithfulness.faithfulness_evaluator({}, output, {"threshold": 0.5})

    assert result.skipped is True
    assert result.passed is None
    assert result.evaluator_name == "faithfulness"
