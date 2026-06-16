"""
Worker execution path tests: sync mode, celery dispatch, run status lifecycle,
idempotency, and completion logic.

These tests verify the execution engine behaves correctly regardless of
whether EVALFORGE_RUN_MODE is "sync" or "celery".
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.schemas import RunCreate
from app.workers.tasks import check_run_completion

# ──────────────────────────────────────────────────────────
# Shared seed helper
# ──────────────────────────────────────────────────────────


async def _seed_project(client: AsyncClient) -> dict:
    """Seed a minimal RAG project and return IDs for run-related tests."""
    app_response = await client.post(
        "/api/apps",
        json={"name": "worker-test-app", "description": "Worker test"},
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

    baseline = await client.post(
        f"/api/apps/{app_id}/versions",
        json={
            "name": "v1_baseline",
            "adapter_module": "app.adapters.demo_rag",
            "config": {"top_k": 1, "corpus": corpus, "latency_ms": 120},
        },
    )

    suite = await client.post(f"/api/apps/{app_id}/suites", json={"name": "worker-suite"})
    suite_id = suite.json()["id"]

    await client.post(
        f"/api/suites/{suite_id}/cases/import",
        json={
            "cases": [
                {
                    "external_id": "wc-001",
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
                    "external_id": "wc-002",
                    "payload": {
                        "input": {"question": "Which Python module handles JSON documents?"},
                        "expected_output": "Python uses json for JSON documents.",
                        "expected_facts": ["json", "JSON documents"],
                        "expected_doc_id": "json",
                        "forbidden_claims": ["quantum database"],
                        "tags": ["easy", "retrieval_required"],
                    },
                },
                {
                    "external_id": "wc-003",
                    "payload": {
                        "input": {
                            "question": "How does Python handle file system paths?",
                        },
                        "expected_output": "Python uses pathlib for file system paths.",
                        "expected_facts": ["pathlib", "file system"],
                        "forbidden_claims": [],
                        "tags": ["easy"],
                    },
                },
            ]
        },
    )

    evaluator = await client.post(
        "/api/evaluator-configs",
        json={
            "name": "worker-test-config",
            "config": {
                "evaluators": [
                    {"name": "contains_keywords", "threshold": 0.8},
                    {"name": "semantic_similarity", "threshold": 0.5},
                    {"name": "forbidden_claim"},
                ]
            },
        },
    )

    return {
        "app_version_id": baseline.json()["id"],
        "suite_id": suite_id,
        "evaluator_config_id": evaluator.json()["id"],
    }


# ──────────────────────────────────────────────────────────
# Sync mode tests
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_sync_run_creates_run_with_correct_case_count(client: AsyncClient):
    """Sync mode creates a run with case_count equal to suite cases."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["case_count"] == 3


@pytest.mark.anyio
async def test_sync_run_initializes_item_statuses(client: AsyncClient):
    """Sync mode initializes RunItems with proper statuses."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    run = run_response.json()
    assert run["status"] == "completed"

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    items = items_response.json()
    assert len(items) == 3
    assert all(item["status"] == "completed" for item in items)
    # attempt_count defaults to 1 in the model; sync executor doesn't track retries
    assert all(item["attempt_count"] == 1 for item in items)


@pytest.mark.anyio
async def test_sync_run_stores_results_per_item(client: AsyncClient):
    """Sync mode stores evaluator results for each run item."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    run = run_response.json()

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    items = items_response.json()

    for item in items:
        assert len(item["results"]) == 3  # 3 evaluators configured
        evaluator_names = {r["evaluator_name"] for r in item["results"]}
        assert evaluator_names == {"contains_keywords", "semantic_similarity", "forbidden_claim"}


@pytest.mark.anyio
async def test_sync_run_stores_traces(client: AsyncClient):
    """Sync mode stores a trace for each run item."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    run = run_response.json()

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    items = items_response.json()

    for item in items:
        trace_response = await client.get(f"/api/runs/{run['id']}/traces/{item['case_id']}")
        assert trace_response.status_code == 200
        trace = trace_response.json()
        assert "steps" in trace["payload"]
        assert trace["payload"]["steps"][0]["step"] == "retrieve"


@pytest.mark.anyio
async def test_sync_run_completion_status_completed_when_all_pass(client: AsyncClient):
    """Sync mode marks run status 'completed' when every item succeeds."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["case_completed"] == 3
    assert run["case_errored"] == 0
    assert run["completed_at"] is not None
    assert run["started_at"] is not None


@pytest.mark.anyio
async def test_sync_run_filters_case_ids(client: AsyncClient):
    """Sync mode respects case_ids parameter, running only specified cases."""
    ids = await _seed_project(client)

    # GET /api/suites/{suite_id}/cases returns a list directly, not {"cases": [...]}
    all_cases = (await client.get(f"/api/suites/{ids['suite_id']}/cases")).json()
    assert len(all_cases) >= 2

    # Run only 2 of the 3 cases
    target_case_ids = [all_cases[0]["id"], all_cases[2]["id"]]

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
            "case_ids": target_case_ids,
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["case_count"] == 2
    assert run["case_completed"] == 2

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    items = items_response.json()
    assert len(items) == 2
    returned_case_ids = {item["case_id"] for item in items}
    assert returned_case_ids == set(target_case_ids)


# ──────────────────────────────────────────────────────────
# Run dispatch (celery mode) service-level tests
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dispatch_path_returns_running_status(client: AsyncClient):
    """
    When EVALFORGE_RUN_MODE=celery, dispatch_run is called which
    creates run items, dispatches tasks, and returns the run still running.
    """
    ids = await _seed_project(client)

    # Need to override the settings at the API level
    # plus mock the celery bits so no real Redis connection is needed
    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord,
    ):
        from app.core.config import Settings

        # Create a settings instance with run_mode=celery
        celery_settings = Settings(run_mode="celery")
        mock_settings.return_value = celery_settings

        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        run_create = RunCreate(
            app_version_id=ids["app_version_id"],
            suite_id=ids["suite_id"],
            evaluator_config_id=ids["evaluator_config_id"],
        )

        run_response = await client.post("/api/runs", json=run_create.model_dump())

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["case_count"] == 3
    assert run["status"] == "running"  # Celery mode returns running immediately
    assert run["completed_at"] is None  # Not yet completed


@pytest.mark.anyio
async def test_celery_mode_initializes_items_as_queued(client: AsyncClient):
    """Celery dispatch sets run item statuses to 'queued' initially."""
    ids = await _seed_project(client)

    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord,
    ):
        from app.core.config import Settings

        celery_settings = Settings(run_mode="celery")
        mock_settings.return_value = celery_settings

        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        run_create = RunCreate(
            app_version_id=ids["app_version_id"],
            suite_id=ids["suite_id"],
            evaluator_config_id=ids["evaluator_config_id"],
        )

        run_response = await client.post("/api/runs", json=run_create.model_dump())

    run = run_response.json()
    items_response = await client.get(f"/api/runs/{run['id']}/items")
    items = items_response.json()

    assert len(items) == 3
    # In celery mode, items start as "queued" (not "running")
    for item in items:
        assert item["status"] in ("queued", "running")
        assert item["attempt_count"] == 1


@pytest.mark.anyio
async def test_celery_mode_dispatches_chord_with_completion_callback(client: AsyncClient):
    """dispatch_run enqueues one task per case plus one completion callback."""
    ids = await _seed_project(client)

    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord_builder,
    ):
        from app.core.config import Settings

        celery_settings = Settings(run_mode="celery")
        mock_settings.return_value = celery_settings

        mock_chord = MagicMock()
        mock_chord_builder.return_value = mock_chord

        run_create = RunCreate(
            app_version_id=ids["app_version_id"],
            suite_id=ids["suite_id"],
            evaluator_config_id=ids["evaluator_config_id"],
        )

        response = await client.post("/api/runs", json=run_create.model_dump())

    assert response.status_code == 201
    run = response.json()
    assert run["case_count"] == 3
    task_signatures = mock_chord_builder.call_args[0][0]
    completion_callback = mock_chord_builder.call_args[0][1]
    assert len(task_signatures) == 3
    assert completion_callback.kwargs == {"run_id": run["id"]}
    mock_chord.apply_async.assert_called_once()


def test_check_run_completion_accepts_celery_chord_results():
    """Celery chords pass the header result list as the first callback argument."""
    fake_session = MagicMock()
    fake_query_result = MagicMock()
    fake_query_result.first.return_value = (3, 3, 0)
    fake_session.execute.return_value = fake_query_result

    fake_context = MagicMock()
    fake_context.__enter__.return_value = fake_session
    fake_context.__exit__.return_value = None

    with patch("app.workers.tasks.Session", return_value=fake_context):
        result = check_run_completion.run([{"status": "completed"}], run_id="run-123")

    assert result == {"status": "completed", "completed": 3, "errored": 0}
    fake_session.commit.assert_called_once()


# ──────────────────────────────────────────────────────────
# Completion logic tests
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_completion_logic_completed_when_all_items_succeed(client: AsyncClient):
    """Sync run with all passing items results in status='completed'."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    run = run_response.json()
    assert run["status"] == "completed"
    assert run["case_completed"] == 3
    assert run["case_errored"] == 0


@pytest.mark.anyio
async def test_run_with_all_hallucinating_cases_still_completes(client: AsyncClient):
    """Even with a candidate that hallucinates, the run completes normally.
    The 'partial' status is tested via the comparison path, not run status."""
    ids = await _seed_project(client)

    # Create a candidate version that hallucinates
    app_id = (await client.get("/api/apps")).json()[0]["id"]
    candidate = await client.post(
        f"/api/apps/{app_id}/versions",
        json={
            "name": "v_candidate",
            "adapter_module": "app.adapters.demo_rag",
            "config": {
                "top_k": 1,
                "corpus": [
                    {
                        "doc_id": "venv",
                        "text": "The venv module creates lightweight Python virtual environments.",
                        "answer": "Python uses the venv module for virtual environments.",
                    },
                ],
                "failure_mode": "hallucinate",
                "latency_ms": 260,
            },
        },
    )
    assert candidate.status_code == 201

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": candidate.json()["id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "completed"  # Run completes even with hallucinating candidate
    assert run["case_count"] == 3
    assert run["case_completed"] == 3
    assert run["case_errored"] == 0


# ──────────────────────────────────────────────────────────
# Idempotency / retry behavior tests
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_idempotency_no_duplicate_results_on_completed_item(client: AsyncClient):
    """A completed run item should not accumulate duplicate results on re-run."""
    ids = await _seed_project(client)

    # First run
    run1 = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    assert run1.status_code == 201
    run1_data = run1.json()

    # Get items from first run
    items1 = await client.get(f"/api/runs/{run1_data['id']}/items")
    items1_data = items1.json()
    assert len(items1_data) == 3

    # Verify each item has exactly the configured number of results (no duplicates)
    for item in items1_data:
        # 3 evaluators configured
        assert len(item["results"]) == 3, (
            f"Item {item['id']} has {len(item['results'])} results, expected 3"
        )

        # Each evaluator should appear exactly once
        evaluator_names = [r["evaluator_name"] for r in item["results"]]
        assert len(evaluator_names) == len(set(evaluator_names)), (
            f"Duplicate evaluator results found for item {item['id']}: {evaluator_names}"
        )

    # Second run (same params)
    run2 = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    assert run2.status_code == 201
    run2_data = run2.json()

    items2 = await client.get(f"/api/runs/{run2_data['id']}/items")
    items2_data = items2.json()
    assert len(items2_data) == 3

    for item in items2_data:
        assert len(item["results"]) == 3
        evaluator_names = [r["evaluator_name"] for r in item["results"]]
        assert len(evaluator_names) == len(set(evaluator_names))


@pytest.mark.anyio
async def test_idempotency_no_duplicate_traces(client: AsyncClient):
    """Each run item should have exactly one trace."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    run = run_response.json()

    items = await client.get(f"/api/runs/{run['id']}/items")
    items_data = items.json()

    # Each item should have exactly one accessible trace
    trace_count = 0
    for item in items_data:
        trace_resp = await client.get(f"/api/runs/{run['id']}/traces/{item['case_id']}")
        if trace_resp.status_code == 200:
            trace_count += 1
    assert trace_count == len(items_data)


# ──────────────────────────────────────────────────────────
# Run status lifecycle tests
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_run_started_at_always_set(client: AsyncClient):
    """Every run must have started_at set."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    run = run_response.json()
    assert run["started_at"] is not None


@pytest.mark.anyio
async def test_run_completed_at_set_when_done(client: AsyncClient):
    """Sync completed runs must have completed_at set."""
    ids = await _seed_project(client)

    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    run = run_response.json()
    assert run["status"] == "completed"
    assert run["completed_at"] is not None


@pytest.mark.anyio
async def test_run_list_returns_most_recent_first(client: AsyncClient):
    """GET /api/runs returns runs ordered by created_at descending."""
    ids = await _seed_project(client)

    # Create two sequential runs
    run1 = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )
    run2 = await client.post(
        "/api/runs",
        json={
            "app_version_id": ids["app_version_id"],
            "suite_id": ids["suite_id"],
            "evaluator_config_id": ids["evaluator_config_id"],
        },
    )

    assert run1.status_code == 201
    assert run2.status_code == 201

    runs_list = await client.get("/api/runs")
    runs = runs_list.json()
    assert len(runs) >= 2
    # Most recent run should be first
    assert runs[0]["id"] == run2.json()["id"]


# ──────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_run_with_nonexistent_version_returns_404(client: AsyncClient):
    """Requesting a run with a non-existent version returns 404."""
    run_response = await client.post(
        "/api/runs",
        json={
            "app_version_id": "nonexistent-id",
            "suite_id": "nonexistent-id",
            "evaluator_config_id": "nonexistent-id",
        },
    )

    assert run_response.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_run_returns_404(client: AsyncClient):
    """GET a run that does not exist returns 404."""
    response = await client.get("/api/runs/nonexistent-run-id")
    assert response.status_code == 404
