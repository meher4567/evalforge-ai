import pytest
from httpx import ASGITransport, AsyncClient

from app.api import health as health_module
from app.main import create_app


@pytest.mark.anyio
async def test_healthz_returns_ok_when_dependencies_are_reachable(monkeypatch):
    async def fake_check_database(database_url: str | None = None) -> bool:
        return True

    async def fake_check_redis(redis_url: str | None = None) -> bool:
        return True

    async def fake_check_database_schema(database_url: str | None = None) -> bool:
        return True

    monkeypatch.setattr(health_module, "check_database", fake_check_database)
    monkeypatch.setattr(health_module, "check_redis", fake_check_redis)
    monkeypatch.setattr(health_module, "check_database_schema", fake_check_database_schema)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api": True,
        "database": True,
        "redis": True,
        "schema": True,
    }


@pytest.mark.anyio
async def test_healthz_returns_degraded_when_a_dependency_is_down(monkeypatch):
    async def fake_check_database(database_url: str | None = None) -> bool:
        return True

    async def fake_check_redis(redis_url: str | None = None) -> bool:
        return False

    async def fake_check_database_schema(database_url: str | None = None) -> bool:
        return True

    monkeypatch.setattr(health_module, "check_database", fake_check_database)
    monkeypatch.setattr(health_module, "check_redis", fake_check_redis)
    monkeypatch.setattr(health_module, "check_database_schema", fake_check_database_schema)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "api": True,
        "database": True,
        "redis": False,
        "schema": True,
    }


@pytest.mark.anyio
async def test_livez_only_reports_process_liveness():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/livez")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api": True}


@pytest.mark.anyio
async def test_readyz_returns_503_when_schema_is_not_migrated(monkeypatch):
    async def reachable(database_url: str | None = None) -> bool:
        return True

    async def schema_missing(database_url: str | None = None) -> bool:
        return False

    monkeypatch.setattr(health_module, "check_database", reachable)
    monkeypatch.setattr(health_module, "check_redis", reachable)
    monkeypatch.setattr(health_module, "check_database_schema", schema_missing)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "api": True,
        "database": True,
        "redis": True,
        "schema": False,
    }
