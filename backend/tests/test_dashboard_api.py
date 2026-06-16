import pytest
from httpx import AsyncClient

from tests.test_run_comparison_api import seed_rag_project


async def seed_computed_comparison(client: AsyncClient) -> dict:
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
    comparison = (
        await client.post(
            "/api/comparisons",
            json={
                "baseline_run_id": baseline_run["id"],
                "candidate_run_id": candidate_run["id"],
            },
        )
    ).json()

    return {
        **ids,
        "baseline_run": baseline_run,
        "candidate_run": candidate_run,
        "comparison": comparison,
    }


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
    assert payload["tracePagination"] == {
        "total": 500,
        "limit": 3,
        "offset": 0,
        "returned": 3,
    }
    assert payload["tagBreakdown"][0]["tag"] == "hallucination_risk"


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_returns_404_without_comparison(client):
    response = await client.get("/api/dashboard/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "No computed comparisons found"


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_aggregates_persisted_comparison(client: AsyncClient):
    ids = await seed_computed_comparison(client)

    response = await client.get("/api/dashboard/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmarkSummary"]["caseCount"] == 2
    assert payload["benchmarkSummary"]["gateVerdict"] == "fail"
    assert payload["metrics"][0]["key"] == "pass_rate"
    assert payload["runs"][0]["id"] == ids["candidate_run"]["id"]
    assert payload["runs"][1]["id"] == ids["baseline_run"]["id"]
    assert payload["traceCases"][0]["id"] == "case-001"
    assert payload["traceCases"][0]["retrievalHit"] is True
    assert payload["traceCases"][0]["chunks"][0]["docId"] == "venv"


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_paginates_failed_trace_cases(client: AsyncClient):
    ids = await seed_computed_comparison(client)

    response = await client.get(
        "/api/dashboard/latest",
        params={
            "comparison_id": ids["comparison"]["id"],
            "failure_limit": 1,
            "failure_offset": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tracePagination"] == {
        "total": 2,
        "limit": 1,
        "offset": 1,
        "returned": 1,
    }
    assert [case["id"] for case in payload["traceCases"]] == ["case-002"]


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_selects_requested_comparison(client: AsyncClient):
    ids = await seed_computed_comparison(client)
    second_baseline_run = (
        await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["baseline_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
            },
        )
    ).json()
    second_comparison = (
        await client.post(
            "/api/comparisons",
            json={
                "baseline_run_id": ids["baseline_run"]["id"],
                "candidate_run_id": second_baseline_run["id"],
            },
        )
    ).json()

    latest_response = await client.get("/api/dashboard/latest")
    selected_response = await client.get(
        "/api/dashboard/latest",
        params={"comparison_id": ids["comparison"]["id"]},
    )

    assert latest_response.status_code == 200
    assert selected_response.status_code == 200
    assert latest_response.json()["benchmarkSummary"]["gateVerdict"] == "pass"
    assert latest_response.json()["runs"][0]["id"] == second_baseline_run["id"]
    assert second_comparison["id"] != ids["comparison"]["id"]
    assert selected_response.json()["benchmarkSummary"]["gateVerdict"] == "fail"
    assert selected_response.json()["runs"][0]["id"] == ids["candidate_run"]["id"]


@pytest.mark.anyio
async def test_latest_dashboard_snapshot_includes_tag_breakdown(client: AsyncClient):
    ids = await seed_computed_comparison(client)

    response = await client.get(
        "/api/dashboard/latest",
        params={"comparison_id": ids["comparison"]["id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tagBreakdown"] == [
        {
            "tag": "easy",
            "baselineCaseCount": 2,
            "candidateCaseCount": 2,
            "candidateFailureCount": 2,
            "candidatePassRate": 0.0,
        }
    ]
