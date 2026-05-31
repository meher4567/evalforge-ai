import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


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
