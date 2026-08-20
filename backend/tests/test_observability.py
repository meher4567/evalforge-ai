from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.observability import _parse_headers
from app.main import create_app


@pytest.mark.anyio
async def test_metrics_endpoint_uses_separate_scrape_credential(monkeypatch):
    monkeypatch.setenv("EVALFORGE_METRICS_TOKEN", "metrics-secret")
    get_settings.cache_clear()
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing = await client.get("/metrics")
        authorized = await client.get(
            "/metrics",
            headers={"Authorization": "Bearer metrics-secret"},
        )

    assert missing.status_code == 401
    assert authorized.status_code == 200
    assert authorized.headers["content-type"].startswith("text/plain")
    assert "evalforge_http_requests_total" in authorized.text
    assert "evalforge_http_request_duration_seconds" in authorized.text
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_cors_preflight_and_trusted_hosts_are_enforced():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        preflight = await client.options(
            "/api/apps",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://untrusted.example",
    ) as client:
        untrusted = await client.get("/livez")

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert untrusted.status_code == 400


def test_render_postgres_url_is_normalized_for_async_sqlalchemy():
    settings = Settings(database_url="postgresql://user:pass@db.example/evalforge")

    assert settings.database_url == ("postgresql+asyncpg://user:pass@db.example/evalforge")


def test_otlp_header_parser_ignores_invalid_items():
    assert _parse_headers("Authorization=secret,invalid,x-team=evalforge") == {
        "Authorization": "secret",
        "x-team": "evalforge",
    }
