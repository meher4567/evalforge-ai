import pytest
from httpx import AsyncClient

from tests.test_run_comparison_api import seed_rag_project


@pytest.mark.anyio
async def test_demo_dashboard_snapshot_returns_benchmark_backed_payload(client):
    response = await client.get("/api/dashboard/demo")

    assert response.status_code == 200
    payload = response.json()

    assert payload["benchmarkSummary"]["caseCount"] == 500
    assert payload["benchmarkSummary"]["gateVerdict"] == "fail"
    assert payload["metrics"][0]["key"] == "pass_rate"
    assert payload["metrics"][0]["candidate"] == 0
    assert payload["metrics"][1]["candidate"] == pytest.approx(0.284951)
    assert payload["runs"][0]["id"] == "run_candidate_500"
    assert payload["traceCases"][0]["id"] == "demo-0001"
    assert payload["traceCases"][0]["chunks"][0]["docId"] == "python-venv"


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_returns_404_without_comparison(client):
    response = await client.get("/api/dashboard/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "No computed comparisons found"


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_aggregates_persisted_comparison(client: AsyncClient):
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
    await client.post(
        "/api/comparisons",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_run_id": candidate_run["id"],
        },
    )

    response = await client.get("/api/dashboard/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmarkSummary"]["caseCount"] == 2
    assert payload["benchmarkSummary"]["gateVerdict"] == "fail"
    assert payload["metrics"][0]["key"] == "pass_rate"
    assert payload["runs"][0]["id"] == candidate_run["id"]
    assert payload["runs"][1]["id"] == baseline_run["id"]
    assert payload["traceCases"][0]["id"] == "case-001"
    assert payload["traceCases"][0]["retrievalHit"] is True
    assert payload["traceCases"][0]["chunks"][0]["docId"] == "venv"
