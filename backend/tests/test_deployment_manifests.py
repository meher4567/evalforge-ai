from __future__ import annotations

import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_declares_api_worker_and_private_datastores():
    blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in blueprint["services"]}
    databases = {database["name"]: database for database in blueprint["databases"]}

    assert services["evalforge-api"]["healthCheckPath"] == "/readyz"
    assert services["evalforge-api"]["runtime"] == "docker"
    assert services["evalforge-worker"]["type"] == "worker"
    assert databases["evalforge-postgres"]["ipAllowList"] == []
    assert databases["evalforge-redis"]["ipAllowList"] == []


def test_vercel_manifest_builds_vite_spa_with_security_headers():
    manifest = json.loads((PROJECT_ROOT / "frontend" / "vercel.json").read_text())
    header_names = {header["key"] for rule in manifest["headers"] for header in rule["headers"]}

    assert manifest["framework"] == "vite"
    assert manifest["outputDirectory"] == "dist"
    assert manifest["rewrites"]
    assert {"X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"} <= header_names
