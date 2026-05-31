from app.adapters.base import AdapterOutput
from app.evaluators.engine import evaluate_case


def make_output() -> AdapterOutput:
    return AdapterOutput(
        answer="Python uses the venv module for virtual environments.",
        retrieved_chunks=[
            {
                "doc_id": "venv",
                "chunk_text": "The venv module creates lightweight virtual environments.",
                "score": 0.8,
            }
        ],
        prompt_used="prompt",
        model_used="deterministic-demo-rag",
        latency_ms=120,
        estimated_cost_usd=0.001,
        trace_steps=[],
    )


def test_evaluator_engine_scores_successful_rag_output():
    case_payload = {
        "expected_output": "Python uses venv for virtual environments.",
        "expected_facts": ["venv", "virtual environments"],
        "expected_doc_id": "venv",
        "forbidden_claims": ["quantum database"],
    }

    results = evaluate_case(
        case_payload,
        make_output(),
        {
            "evaluators": [
                {"name": "contains_keywords", "threshold": 0.8},
                {"name": "semantic_similarity", "threshold": 0.5},
                {"name": "retrieval_hit_rate"},
                {"name": "forbidden_claim"},
                {"name": "latency_threshold", "threshold_ms": 200},
                {"name": "cost_threshold", "threshold_usd": 0.01},
            ]
        },
    )

    by_name = {result.evaluator_name: result for result in results}

    assert by_name["contains_keywords"].passed is True
    assert by_name["semantic_similarity"].passed is True
    assert by_name["retrieval_hit_rate"].score == 1.0
    assert by_name["forbidden_claim"].passed is True
    assert by_name["latency_threshold"].passed is True
    assert by_name["cost_threshold"].passed is True


def test_evaluator_engine_marks_inapplicable_evaluator_as_skipped():
    results = evaluate_case(
        {"expected_output": "hello"},
        make_output(),
        {"evaluators": [{"name": "retrieval_hit_rate"}]},
    )

    assert results[0].skipped is True
    assert results[0].score is None
    assert results[0].passed is None


def test_forbidden_claim_evaluator_fails_bad_output():
    output = make_output()
    output.answer = "Python uses a quantum database for virtual environments."

    results = evaluate_case(
        {"forbidden_claims": ["quantum database"]},
        output,
        {"evaluators": [{"name": "forbidden_claim"}]},
    )

    assert results[0].passed is False
    assert results[0].score == 0.0
