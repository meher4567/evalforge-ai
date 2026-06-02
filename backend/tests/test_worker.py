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
