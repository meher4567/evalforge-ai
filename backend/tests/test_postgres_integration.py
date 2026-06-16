import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.mark.anyio
async def test_postgres_backed_api_run_executes_end_to_end():
    database_url = os.environ.get("EVALFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set EVALFORGE_TEST_DATABASE_URL to run the Postgres integration test")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    unique = uuid4().hex[:8]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_response = await client.post(
            "/api/apps",
            json={"name": f"postgres-rag-{unique}", "description": "Postgres integration"},
        )
        assert app_response.status_code == 201
        app_id = app_response.json()["id"]

        version_response = await client.post(
            f"/api/apps/{app_id}/versions",
            json={
                "name": "v1",
                "adapter_module": "app.adapters.demo_rag",
                "config": {
                    "top_k": 1,
                    "corpus": [
                        {
                            "doc_id": "venv",
                            "text": (
                                "The venv module creates lightweight Python virtual environments."
                            ),
                            "answer": "Python uses venv for virtual environments.",
                        }
                    ],
                },
            },
        )
        suite_response = await client.post(f"/api/apps/{app_id}/suites", json={"name": "suite"})
        suite_id = suite_response.json()["id"]
        await client.post(
            f"/api/suites/{suite_id}/cases/import",
            json={
                "cases": [
                    {
                        "external_id": f"postgres-case-{unique}",
                        "payload": {
                            "input": {
                                "question": "Which Python module creates virtual environments?"
                            },
                            "expected_output": "Python uses venv for virtual environments.",
                            "expected_facts": ["venv", "virtual environments"],
                            "expected_doc_id": "venv",
                        },
                    }
                ]
            },
        )
        evaluator_response = await client.post(
            "/api/evaluator-configs",
            json={
                "name": f"postgres-eval-{unique}",
                "config": {
                    "evaluators": [
                        {"name": "token_f1_overlap", "threshold": 0.5},
                        {"name": "retrieval_hit_rate"},
                    ]
                },
            },
        )

        run_response = await client.post(
            "/api/runs",
            json={
                "app_version_id": version_response.json()["id"],
                "suite_id": suite_id,
                "evaluator_config_id": evaluator_response.json()["id"],
            },
        )

        assert run_response.status_code == 201
        run = run_response.json()
        assert run["status"] == "completed"
        assert run["case_completed"] == 1

        items_response = await client.get(f"/api/runs/{run['id']}/items")
        assert items_response.status_code == 200
        assert len(items_response.json()[0]["results"]) == 2

    app.dependency_overrides.clear()
    await engine.dispose()
