import tomllib
from pathlib import Path

import yaml


def test_docker_compose_defines_celery_worker_service():
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    worker = compose["services"].get("worker")

    assert worker is not None
    assert "celery" in " ".join(worker["command"])
    assert worker["environment"]["EVALFORGE_RUN_MODE"] == "celery"
    assert "postgres" in worker["depends_on"]
    assert "redis" in worker["depends_on"]


def test_backend_dockerfile_uses_lightweight_runtime_dependency_profile():
    project_root = Path(__file__).resolve().parents[2]
    dockerfile = (project_root / "backend" / "Dockerfile").read_text(encoding="utf-8")
    pyproject = tomllib.loads((project_root / "backend" / "pyproject.toml").read_text())
    runtime_dependencies = set(pyproject["project"]["dependencies"])
    ml_dependencies = set(pyproject["dependency-groups"]["ml"])

    assert "uv sync --no-dev --no-group ml" in dockerfile
    assert not any(
        dependency.startswith("sentence-transformers") for dependency in runtime_dependencies
    )
    assert not any(dependency.startswith("transformers") for dependency in runtime_dependencies)
    assert any(dependency.startswith("sentence-transformers") for dependency in ml_dependencies)
