import pytest


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
