import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_app_version_suite_and_case_import_flow(client: AsyncClient):
    app_response = await client.post(
        "/api/apps",
        json={"name": "demo-rag", "description": "Demo RAG application"},
    )
    assert app_response.status_code == 201
    app_payload = app_response.json()

    version_response = await client.post(
        f"/api/apps/{app_payload['id']}/versions",
        json={
            "name": "v1_baseline",
            "adapter_module": "app.adapters.demo_rag",
            "config": {"top_k": 3, "prompt": "answer from context"},
        },
    )
    assert version_response.status_code == 201
    assert version_response.json()["name"] == "v1_baseline"

    suite_response = await client.post(
        f"/api/apps/{app_payload['id']}/suites",
        json={"name": "demo-suite"},
    )
    assert suite_response.status_code == 201
    suite_payload = suite_response.json()

    import_response = await client.post(
        f"/api/suites/{suite_payload['id']}/cases/import",
        json={
            "cases": [
                {
                    "external_id": "case-001",
                    "payload": {
                        "input": {"question": "What does Python use for virtual environments?"},
                        "expected_output": "venv",
                        "expected_facts": ["venv"],
                        "tags": ["easy", "retrieval_required"],
                    },
                }
            ]
        },
    )
    assert import_response.status_code == 201
    assert import_response.json() == {"imported": 1, "errors": []}

    cases_response = await client.get(f"/api/suites/{suite_payload['id']}/cases")
    assert cases_response.status_code == 200
    cases = cases_response.json()
    assert len(cases) == 1
    assert cases[0]["external_id"] == "case-001"
    assert cases[0]["payload"]["expected_facts"] == ["venv"]

    summary_response = await client.get(f"/api/suites/{suite_payload['id']}/summary")
    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "case_count": 1,
        "tag_distribution": {"easy": 1, "retrieval_required": 1},
    }


@pytest.mark.anyio
async def test_duplicate_app_name_returns_conflict(client: AsyncClient):
    payload = {"name": "demo-rag", "description": "Demo RAG application"}

    first_response = await client.post("/api/apps", json=payload)
    second_response = await client.post("/api/apps", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "App name already exists"


@pytest.mark.anyio
async def test_evaluator_config_can_be_created_and_listed(client: AsyncClient):
    create_response = await client.post(
        "/api/evaluator-configs",
        json={
            "name": "default-rag",
            "config": {
                "evaluators": [
                    {"name": "contains_keywords", "threshold": 0.8},
                    {"name": "latency_threshold", "threshold_ms": 2000},
                ]
            },
        },
    )
    assert create_response.status_code == 201

    list_response = await client.get("/api/evaluator-configs")

    assert list_response.status_code == 200
    configs = list_response.json()
    assert len(configs) == 1
    assert configs[0]["name"] == "default-rag"


@pytest.mark.anyio
async def test_evaluator_config_rejects_unknown_and_duplicate_evaluators(client: AsyncClient):
    unknown = await client.post(
        "/api/evaluator-configs",
        json={"name": "unknown", "config": {"evaluators": [{"name": "made_up"}]}},
    )
    duplicate = await client.post(
        "/api/evaluator-configs",
        json={
            "name": "duplicate",
            "config": {
                "evaluators": [
                    {"name": "exact_match"},
                    {"name": "exact_match"},
                ]
            },
        },
    )

    assert unknown.status_code == 422
    assert unknown.json()["detail"] == "Unknown evaluator: made_up"
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"] == "Duplicate evaluator: exact_match"


@pytest.mark.anyio
async def test_evaluator_capabilities_report_optional_dependencies(client: AsyncClient):
    response = await client.get("/api/evaluators")

    assert response.status_code == 200
    capabilities = {item["name"]: item for item in response.json()}
    assert capabilities["token_f1_overlap"]["available"] is True
    assert capabilities["semantic_similarity"]["alias_for"] == "token_f1_overlap"
    assert capabilities["semantic_similarity"]["deprecated"] is True
    assert capabilities["faithfulness"]["dependency_group"] == "ml"


@pytest.mark.anyio
async def test_registry_lists_are_paginated(client: AsyncClient):
    apps = []
    for index in range(3):
        response = await client.post(
            "/api/apps",
            json={"name": f"app-{index}", "description": "pagination fixture"},
        )
        assert response.status_code == 201
        apps.append(response.json())

    page = await client.get("/api/apps", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    assert len(page.json()) == 1

    app_id = apps[0]["id"]
    for index in range(2):
        version = await client.post(
            f"/api/apps/{app_id}/versions",
            json={
                "name": f"version-{index}",
                "adapter_module": "app.adapters.demo_rag",
                "config": {},
            },
        )
        suite = await client.post(f"/api/apps/{app_id}/suites", json={"name": f"suite-{index}"})
        assert version.status_code == 201
        assert suite.status_code == 201

    versions = await client.get(f"/api/apps/{app_id}/versions", params={"limit": 1, "offset": 1})
    suites = await client.get(f"/api/apps/{app_id}/suites", params={"limit": 1, "offset": 1})
    assert len(versions.json()) == 1
    assert len(suites.json()) == 1

    invalid = await client.get("/api/apps", params={"limit": 0})
    assert invalid.status_code == 422


@pytest.mark.anyio
async def test_app_version_rejects_unapproved_adapter_module(client: AsyncClient):
    app = (
        await client.post("/api/apps", json={"name": "adapter-policy", "description": ""})
    ).json()

    response = await client.post(
        f"/api/apps/{app['id']}/versions",
        json={
            "name": "unsafe",
            "adapter_module": "os",
            "config": {},
        },
    )

    assert response.status_code == 422
    assert "is not allowed" in response.json()["detail"]


@pytest.mark.anyio
async def test_case_tag_filter_applies_pagination_after_filtering(client: AsyncClient):
    app = (await client.post("/api/apps", json={"name": "tags", "description": ""})).json()
    suite = (await client.post(f"/api/apps/{app['id']}/suites", json={"name": "tagged"})).json()
    response = await client.post(
        f"/api/suites/{suite['id']}/cases/import",
        json={
            "cases": [
                {
                    "external_id": "match-1",
                    "payload": {"input": "one", "tags": ["target"]},
                },
                {
                    "external_id": "skip",
                    "payload": {"input": "two", "tags": ["other"]},
                },
                {
                    "external_id": "match-2",
                    "payload": {"input": "three", "tags": ["target"]},
                },
            ]
        },
    )
    assert response.json() == {"imported": 3, "errors": []}

    page = await client.get(
        f"/api/suites/{suite['id']}/cases",
        params={"tag": "target", "limit": 1, "offset": 1},
    )

    assert page.status_code == 200
    assert [case["external_id"] for case in page.json()] == ["match-2"]
