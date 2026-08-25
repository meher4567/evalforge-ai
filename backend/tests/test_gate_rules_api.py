import pytest
from httpx import AsyncClient

from app.services.comparison import DEFAULT_GATE_RULES
from tests.test_run_comparison_api import seed_rag_project


@pytest.mark.anyio
async def test_gate_rules_crud_and_validation(client: AsyncClient):
    created = await client.post(
        "/api/gate-rules",
        json={"name": "relaxed", "rules": DEFAULT_GATE_RULES},
    )

    assert created.status_code == 201
    gate_rule = created.json()
    assert gate_rule["name"] == "relaxed"
    assert gate_rule["rules"]["pass_rate"]["tolerance"] == 0.02

    fetched = await client.get(f"/api/gate-rules/{gate_rule['id']}")
    listed = await client.get("/api/gate-rules")
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == gate_rule["id"]

    invalid = await client.post(
        "/api/gate-rules",
        json={
            "name": "invalid",
            "rules": {"pass_rate": {"direction": "sideways", "tolerance": -1}},
        },
    )
    assert invalid.status_code == 422


@pytest.mark.anyio
async def test_comparison_honours_persisted_custom_gate_rules(client: AsyncClient):
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
    relaxed_rules = {
        "pass_rate": {
            **DEFAULT_GATE_RULES["pass_rate"],
            "tolerance": 10_000.0,
        }
    }
    gate_rule = (
        await client.post(
            "/api/gate-rules",
            json={"name": "allow-demo-regression", "rules": relaxed_rules},
        )
    ).json()

    comparison = await client.post(
        "/api/comparisons",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_run_id": candidate_run["id"],
            "gate_rules_id": gate_rule["id"],
        },
    )

    assert comparison.status_code == 201
    assert comparison.json()["report"]["gate_verdict"] == "pass"

    dashboard = await client.get(
        "/api/dashboard/latest", params={"comparison_id": comparison.json()["id"]}
    )
    assert dashboard.status_code == 200
    metrics_by_key = {metric["key"]: metric for metric in dashboard.json()["metrics"]}
    assert metrics_by_key["pass_rate"]["tolerance"] == 10_000.0
    assert metrics_by_key["pass_rate"]["status"] == "pass"
    assert metrics_by_key["semantic_similarity"]["status"] == "not_evaluated"
    assert {rule["verdict"] for rule in dashboard.json()["gateRules"]} == {"pass"}


@pytest.mark.anyio
async def test_comparison_rejects_missing_gate_rules(client: AsyncClient):
    ids = await seed_rag_project(client)
    run_payload = {
        "app_version_id": ids["baseline_version_id"],
        "suite_id": ids["suite_id"],
        "evaluator_config_id": ids["evaluator_config_id"],
    }
    baseline = (await client.post("/api/runs", json=run_payload)).json()
    candidate = (await client.post("/api/runs", json=run_payload)).json()

    response = await client.post(
        "/api/comparisons",
        json={
            "baseline_run_id": baseline["id"],
            "candidate_run_id": candidate["id"],
            "gate_rules_id": "missing",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Gate rules not found"
