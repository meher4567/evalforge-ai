from app.demo.dataset import build_demo_corpus, build_eval_cases


def test_demo_dataset_generates_500_cases_with_required_tags():
    cases = build_eval_cases(500)

    assert len(cases) == 500
    assert cases[0]["external_id"] == "demo-0001"
    assert all("input" in case["payload"] for case in cases)
    assert all("expected_facts" in case["payload"] for case in cases)

    tags = {tag for case in cases for tag in case["payload"]["tags"]}
    assert {"easy", "retrieval_required", "hallucination_risk", "reasoning_required"} <= tags


def test_demo_corpus_contains_stable_answer_fields():
    corpus = build_demo_corpus()

    assert len(corpus) >= 10
    assert {"doc_id", "text", "answer"} <= set(corpus[0])
