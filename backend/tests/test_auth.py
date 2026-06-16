import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.mark.anyio
async def test_health_remains_public_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("EVALFORGE_API_KEY", "secret")
    get_settings.cache_clear()
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_data_apis_require_key_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("EVALFORGE_API_KEY", "secret")
    get_settings.cache_clear()
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
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing_response = await client.get("/api/apps")
        header_response = await client.get(
            "/api/apps",
            headers={"X-EvalForge-Api-Key": "secret"},
        )

    assert missing_response.status_code == 401
    assert header_response.status_code != 401

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()
