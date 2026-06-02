from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from tests.test_run_comparison_api import seed_rag_project


@pytest.mark.anyio
async def test_celery_api_dispatches_chord_with_immutable_completion_callback(
    client: AsyncClient,
):
    ids = await seed_rag_project(client)

    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord_builder,
    ):
        mock_settings.return_value = Settings(run_mode="celery")
        mock_chord = MagicMock()
        mock_chord_builder.return_value = mock_chord

        response = await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["baseline_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
            },
        )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "running"

    task_signatures, completion_callback = mock_chord_builder.call_args.args
    assert len(task_signatures) == 2
    assert completion_callback.immutable is True
    assert completion_callback.kwargs == {"run_id": run["id"]}
    mock_chord.apply_async.assert_called_once()


@pytest.mark.anyio
async def test_celery_api_leaves_run_items_queued_until_worker_finishes(
    client: AsyncClient,
):
    ids = await seed_rag_project(client)

    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord_builder,
    ):
        mock_settings.return_value = Settings(run_mode="celery")
        mock_chord_builder.return_value = MagicMock()

        response = await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["baseline_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
            },
        )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "running"
    assert run["case_count"] == 2
    assert run["case_completed"] == 0
    assert run["case_errored"] == 0
    assert run["completed_at"] is None

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    assert items_response.status_code == 200
    items = items_response.json()
    assert len(items) == 2
    assert all(item["status"] == "queued" for item in items)
    assert all(item["results"] == [] for item in items)


@pytest.mark.anyio
async def test_celery_api_dispatches_only_requested_case_subset(
    client: AsyncClient,
):
    ids = await seed_rag_project(client)
    cases_response = await client.get(f"/api/suites/{ids['suite_id']}/cases")
    selected_case = cases_response.json()[0]

    with (
        patch("app.api.runs.get_settings") as mock_settings,
        patch("app.services.run_dispatcher.chord") as mock_chord_builder,
    ):
        mock_settings.return_value = Settings(run_mode="celery")
        mock_chord = MagicMock()
        mock_chord_builder.return_value = mock_chord

        response = await client.post(
            "/api/runs",
            json={
                "app_version_id": ids["baseline_version_id"],
                "suite_id": ids["suite_id"],
                "evaluator_config_id": ids["evaluator_config_id"],
                "case_ids": [selected_case["id"]],
            },
        )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "running"
    assert run["case_count"] == 1

    task_signatures, _completion_callback = mock_chord_builder.call_args.args
    assert len(task_signatures) == 1
    mock_chord.apply_async.assert_called_once()

    items_response = await client.get(f"/api/runs/{run['id']}/items")
    assert items_response.status_code == 200
    items = items_response.json()
    assert [item["case_id"] for item in items] == [selected_case["id"]]
