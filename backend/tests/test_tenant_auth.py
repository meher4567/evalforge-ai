from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

BOOTSTRAP_PAYLOAD = {
    "email": "owner@example.com",
    "password": "correct-horse-battery-staple",
    "display_name": "Owner",
    "organization_name": "Alpha Org",
    "organization_slug": "alpha",
}


@pytest.fixture
async def tenant_client(monkeypatch):
    monkeypatch.setenv("EVALFORGE_BOOTSTRAP_TOKEN", "bootstrap-secret")
    monkeypatch.setenv("EVALFORGE_AUTH_TOKEN_PEPPER", "test-token-pepper")
    monkeypatch.delenv("EVALFORGE_API_KEY", raising=False)
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _bootstrap(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/auth/bootstrap",
        headers={"X-EvalForge-Bootstrap-Token": "bootstrap-secret"},
        json=BOOTSTRAP_PAYLOAD,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_bootstrap_login_logout_and_one_time_guard(tenant_client: AsyncClient):
    forbidden = await tenant_client.post(
        "/api/auth/bootstrap",
        headers={"X-EvalForge-Bootstrap-Token": "wrong"},
        json=BOOTSTRAP_PAYLOAD,
    )
    assert forbidden.status_code == 403

    bootstrapped = await _bootstrap(tenant_client)
    assert bootstrapped["user"]["email"] == "owner@example.com"
    assert bootstrapped["organization"]["slug"] == "alpha"
    assert bootstrapped["role"] == "owner"
    assert bootstrapped["access_token"].startswith("efs_")

    repeated = await tenant_client.post(
        "/api/auth/bootstrap",
        headers={"X-EvalForge-Bootstrap-Token": "bootstrap-secret"},
        json=BOOTSTRAP_PAYLOAD,
    )
    assert repeated.status_code == 409

    invalid_login = await tenant_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "not-the-password"},
    )
    assert invalid_login.status_code == 401
    assert invalid_login.json()["detail"] == "Invalid email, password, or organization"

    login = await tenant_client.post(
        "/api/auth/login",
        json={
            "email": "OWNER@example.com",
            "password": BOOTSTRAP_PAYLOAD["password"],
            "organization_slug": "alpha",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert (await tenant_client.get("/api/auth/me", headers=_auth(token))).status_code == 200
    changed = await tenant_client.post(
        "/api/auth/change-password",
        headers=_auth(token),
        json={
            "current_password": BOOTSTRAP_PAYLOAD["password"],
            "new_password": "a-new-long-unique-password",
        },
    )
    assert changed.status_code == 204
    old_password = await tenant_client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": BOOTSTRAP_PAYLOAD["password"],
            "organization_slug": "alpha",
        },
    )
    assert old_password.status_code == 401
    new_password = await tenant_client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": "a-new-long-unique-password",
            "organization_slug": "alpha",
        },
    )
    assert new_password.status_code == 200
    assert (await tenant_client.post("/api/auth/logout", headers=_auth(token))).status_code == 204
    assert (await tenant_client.get("/api/auth/me", headers=_auth(token))).status_code == 401


@pytest.mark.anyio
async def test_tenant_isolation_rbac_and_api_key_revocation(tenant_client: AsyncClient):
    owner = await _bootstrap(tenant_client)
    alpha_token = owner["access_token"]

    alpha_app = await tenant_client.post(
        "/api/apps",
        headers=_auth(alpha_token),
        json={"name": "shared-name", "description": "alpha"},
    )
    assert alpha_app.status_code == 201

    beta = await tenant_client.post(
        "/api/organizations",
        headers=_auth(alpha_token),
        json={"name": "Beta Org", "slug": "beta"},
    )
    assert beta.status_code == 201
    switched = await tenant_client.post(
        "/api/auth/switch-organization",
        headers=_auth(alpha_token),
        json={"organization_slug": "beta"},
    )
    assert switched.status_code == 200
    beta_token = switched.json()["access_token"]
    beta_app = await tenant_client.post(
        "/api/apps",
        headers=_auth(beta_token),
        json={"name": "shared-name", "description": "beta"},
    )
    assert beta_app.status_code == 201

    alpha_list = await tenant_client.get("/api/apps", headers=_auth(alpha_token))
    beta_list = await tenant_client.get("/api/apps", headers=_auth(beta_token))
    assert [item["description"] for item in alpha_list.json()] == ["alpha"]
    assert [item["description"] for item in beta_list.json()] == ["beta"]
    cross_tenant = await tenant_client.get(
        f"/api/apps/{alpha_app.json()['id']}", headers=_auth(beta_token)
    )
    assert cross_tenant.status_code == 404

    member = await tenant_client.post(
        "/api/organizations/current/members",
        headers=_auth(alpha_token),
        json={
            "email": "viewer@example.com",
            "display_name": "Viewer",
            "password": "viewer-password-long-enough",
            "role": "viewer",
        },
    )
    assert member.status_code == 201
    viewer_id = member.json()["user"]["id"]
    viewer_login = await tenant_client.post(
        "/api/auth/login",
        json={
            "email": "viewer@example.com",
            "password": "viewer-password-long-enough",
            "organization_slug": "alpha",
        },
    )
    viewer_token = viewer_login.json()["access_token"]
    assert (await tenant_client.get("/api/apps", headers=_auth(viewer_token))).status_code == 200
    denied = await tenant_client.post(
        "/api/apps",
        headers=_auth(viewer_token),
        json={"name": "viewer-cannot-create"},
    )
    assert denied.status_code == 403

    key_response = await tenant_client.post(
        "/api/auth/api-keys",
        headers=_auth(viewer_token),
        json={"name": "ci-key", "expires_in_days": 30},
    )
    assert key_response.status_code == 201
    key_payload = key_response.json()
    api_key = key_payload["api_key"]
    assert api_key.startswith("efk_")
    assert (await tenant_client.get("/api/apps", headers=_auth(api_key))).status_code == 200

    promoted = await tenant_client.patch(
        f"/api/organizations/current/members/{viewer_id}",
        headers=_auth(alpha_token),
        json={"role": "evaluator"},
    )
    assert promoted.status_code == 200
    now_allowed = await tenant_client.post(
        "/api/apps",
        headers=_auth(api_key),
        json={"name": "evaluator-created"},
    )
    assert now_allowed.status_code == 201

    revoked = await tenant_client.delete(
        f"/api/auth/api-keys/{key_payload['id']}",
        headers=_auth(viewer_token),
    )
    assert revoked.status_code == 204
    assert (await tenant_client.get("/api/apps", headers=_auth(api_key))).status_code == 401


@pytest.mark.anyio
async def test_repeated_password_failures_lock_the_account(tenant_client: AsyncClient):
    await _bootstrap(tenant_client)
    for _attempt in range(5):
        failed = await tenant_client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.com",
                "password": "incorrect-password",
                "organization_slug": "alpha",
            },
        )
        assert failed.status_code == 401

    locked = await tenant_client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": BOOTSTRAP_PAYLOAD["password"],
            "organization_slug": "alpha",
        },
    )
    assert locked.status_code == 401
    assert locked.json()["detail"] == "Invalid email, password, or organization"
