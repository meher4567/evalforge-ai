import pytest
from httpx import AsyncClient


async def seed_rag_project(client: AsyncClient):
    app_response = await client.post(
        "/api/apps",
        json={"name": "demo-rag", "description": "Demo RAG application"},
    )
    app_id = app_response.json()["id"]

    corpus = [
        {
            "doc_id": "venv",
            "text": "The venv module creates lightweight Python virtual environments.",
            "answer": "Python uses the venv module for virtual environments.",
        },
        {
            "doc_id": "json",
            "text": "The json module encodes and decodes JSON documents.",
            "answer": "Python uses the json module for JSON documents.",
        },
    ]

    baseline_response = await client.post(
        f"/api/apps/{app_id}/versions",
        json={
            "name": "v1_baseline",
            "adapter_module": "app.adapters.demo_rag",
            "config": {"top_k": 1, "corpus": corpus, "latency_ms": 120},
        },
    )
    candidate_response = await client.post(
        f"/api/apps/{app_id}/versions",
        json={
            "name": "v2_bad_candidate",
            "adapter_module": "app.adapters.demo_rag",
            "config": {
                "top_k": 1,
                "corpus": corpus,
                "failure_mode": "hallucinate",
                "latency_ms": 260,
            },
        },
    )

    suite_response = await client.post(f"/api/apps/{app_id}/suites", json={"name": "demo-suite"})
    suite_id = suite_response.json()["id"]

    await client.post(
        f"/api/suites/{suite_id}/cases/import",
        json={
            "cases": [
                {
                    "external_id": "case-001",
                    "payload": {
                        "input": {"question": "Which Python module creates virtual environments?"},
                        "expected_output": "Python uses venv for virtual environments.",
                        "expected_facts": ["venv", "virtual environments"],
                        "expected_doc_id": "venv",
                        "forbidden_claims": ["quantum database"],
                        "tags": ["easy", "retrieval_required"],
                    },
                },
                {
                    "external_id": "case-002",
                    "payload": {
                        "input": {"question": "Which Python module handles JSON documents?"},
                        "expected_output": "Python uses json for JSON documents.",
                        "expected_facts": ["json", "JSON documents"],
                        "expected_doc_id": "json",
                        "forbidden_claims": ["quantum database"],
                        "tags": ["easy", "retrieval_required"],
                    },
                },
            ]
        },
    )

    evaluator_response = await client.post(
        "/api/evaluator-configs",
        json={
            "name": "default-rag",
            "config": {
                "evaluators": [
                    {"name": "contains_keywords", "threshold": 0.8},
                    {"name": "semantic_similarity", "threshold": 0.5},
                    {"name": "retrieval_hit_rate"},
                    {"name": "forbidden_claim"},
                    {"name": "latency_threshold", "threshold_ms": 200},
                    {"name": "cost_threshold", "threshold_usd": 0.01},
                ]
            },
        },
    )

    return {
        "baseline_version_id": baseline_response.json()["id"],
        "candidate_version_id": candidate_response.json()["id"],
        "suite_id": suite_id,
        "evaluator_config_id": evaluator_response.json()["id"],
    }


@pytest.mark.anyio
async def test_run_execution_stores_items_results_and_traces(client: AsyncClient):
    ids = await seed_rag_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["baseline_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["case_count"] == 2
    assert run["case_completed"] == 2

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    assert items_response.status_code == 200
    items = items_response.json()
    assert len(items) == 2
    assert all(item["status"] == "completed" for item in items)
    assert all(len(item["results"]) == 6 for item in items)

    trace_response = await client.get(f"/api/runs/{run['id']}/traces/{items[0]['case_id']}")
    assert trace_response.status_code == 200
    assert trace_response.json()["payload"]["steps"][0]["step"] == "retrieve"


@pytest.mark.anyio
async def test_comparison_detects_bad_candidate_regression(client: AsyncClient):
    ids = await seed_rag_project(client)

    baseline_run = (
        await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["baseline_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
            },
        )
    ).json()
    candidate_run = (
        await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["candidate_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
            },
        )
    ).json()

    comparison_response = await client.post(
        "/api/comparisons",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_run_id": candidate_run["id"],
        },
    )

    assert comparison_response.status_code == 201
    comparison = comparison_response.json()
    assert comparison["status"] == "computed"
    assert comparison["report"]["gate_verdict"] == "fail"
    assert comparison["report"]["metrics"]["pass_rate"]["candidate_point"] < 1.0

    gate_response = await client.get(f"/api/comparisons/{comparison['id']}/gate-decision")
    assert gate_response.status_code == 200
    assert gate_response.json()["verdict"] == "fail"
