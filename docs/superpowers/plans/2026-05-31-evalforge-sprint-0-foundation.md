# EvalForge Sprint 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reproducible backend foundation for EvalForge AI with FastAPI, `uv`, PostgreSQL, Redis, Docker Compose, tests, linting, and beginner-friendly project documentation.

**Architecture:** The backend is a small FastAPI service with an app factory, a `/healthz` route, configuration loaded from environment variables, and isolated health helpers for PostgreSQL and Redis. Docker Compose runs the backend, PostgreSQL, and Redis together so later sprints can add database models and Celery workers without reorganizing the project.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy async engine, asyncpg, redis-py asyncio, uvicorn, `uv`, PostgreSQL with pgvector image, Redis, Docker Compose, pytest, httpx/TestClient, ruff.

---

## File Structure Map

- Create: `.gitignore`  
  Keeps Python, uv, editor, Docker, and OS-generated files out of source control.

- Create: `backend/pyproject.toml`  
  Defines the backend Python package, runtime dependencies, dev dependencies, pytest config, and ruff config.

- Create: `backend/.env.example`  
  Documents local environment variables without storing secrets.

- Create: `backend/app/__init__.py`  
  Marks `app` as a Python package.

- Create: `backend/app/main.py`  
  FastAPI entry point and app factory.

- Create: `backend/app/api/__init__.py`  
  Marks API route modules as a package.

- Create: `backend/app/api/health.py`  
  Defines `GET /healthz` and its response model.

- Create: `backend/app/core/__init__.py`  
  Marks core infrastructure helpers as a package.

- Create: `backend/app/core/config.py`  
  Central settings object loaded from environment variables.

- Create: `backend/app/core/redis.py`  
  Redis connectivity helper for health checks.

- Create: `backend/app/db/__init__.py`  
  Marks database helpers as a package.

- Create: `backend/app/db/health.py`  
  PostgreSQL connectivity helper for health checks.

- Create: `backend/tests/__init__.py`  
  Marks tests as a Python package.

- Create: `backend/tests/test_health.py`  
  Unit tests for healthy and degraded `/healthz` responses.

- Create: `backend/Dockerfile`  
  Builds the backend container using `uv`.

- Create: `docker-compose.yml`  
  Runs PostgreSQL, Redis, and the backend API together.

- Create: `README.md`  
  Documents the project purpose, Sprint 0 architecture, and local commands.

---

### Task 1: Initialize Source Control and Ignore Generated Files

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Verify whether this workspace is already a Git repository**

Run:

```powershell
git rev-parse --is-inside-work-tree
```

Expected if not initialized:

```text
fatal: not a git repository (or any of the parent directories): .git
```

- [ ] **Step 2: Initialize Git after user approval**

Run only after explicit approval:

```powershell
git init
```

Expected:

```text
Initialized empty Git repository in D:/CKXJ/ML/TD_MAIN_00/EvalForge-AI/.git/
```

- [ ] **Step 3: Create `.gitignore`**

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
env/

# uv
*.egg-info/

# Environment files
.env
backend/.env

# Node / frontend
node_modules/
dist/
build/

# Docker / local data
.docker/
docker-data/

# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
```

- [ ] **Step 4: Commit the ignore file**

Run:

```powershell
git add .gitignore
git commit -m "chore: initialize repository ignore rules"
```

Expected:

```text
[main/root-commit ...] chore: initialize repository ignore rules
```

---

### Task 2: Create Backend Python Project Metadata

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create backend directories**

Run:

```powershell
New-Item -ItemType Directory -Force -Path `
  backend\app\api, `
  backend\app\core, `
  backend\app\db, `
  backend\app\models, `
  backend\app\schemas, `
  backend\app\services, `
  backend\app\evaluators, `
  backend\app\workers, `
  backend\tests | Out-Null
```

Expected: command exits successfully and creates the directories.

- [ ] **Step 2: Create Python package marker files**

Create these empty files:

```text
backend/app/__init__.py
backend/app/api/__init__.py
backend/app/core/__init__.py
backend/app/db/__init__.py
backend/tests/__init__.py
```

- [ ] **Step 3: Create `backend/pyproject.toml`**

Create `backend/pyproject.toml`:

```toml
[project]
name = "evalforge-backend"
version = "0.1.0"
description = "Backend API for EvalForge AI"
readme = "../README.md"
requires-python = ">=3.11"
dependencies = [
    "asyncpg>=0.29.0",
    "fastapi>=0.115.0",
    "pydantic-settings>=2.6.0",
    "redis>=5.0.8",
    "sqlalchemy[asyncio]>=2.0.35",
    "uvicorn[standard]>=0.30.6",
]

[dependency-groups]
dev = [
    "httpx>=0.27.2",
    "pytest>=8.3.3",
    "ruff>=0.6.8",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"
```

- [ ] **Step 4: Create `backend/.env.example`**

Create `backend/.env.example`:

```env
EVALFORGE_ENVIRONMENT=development
EVALFORGE_DATABASE_URL=postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge
EVALFORGE_REDIS_URL=redis://localhost:6379/0
EVALFORGE_HEALTH_CHECK_TIMEOUT_SECONDS=2.0
```

- [ ] **Step 5: Install dependencies and create `uv.lock`**

Run:

```powershell
uv sync --directory backend
```

Expected:

```text
Resolved ...
Installed ...
```

The exact package count may vary by platform. The important result is that `backend/uv.lock` and `backend/.venv/` exist.

- [ ] **Step 6: Commit backend project metadata**

Run:

```powershell
git add backend/pyproject.toml backend/uv.lock backend/.env.example backend/app backend/tests
git commit -m "chore: create backend python project"
```

Expected:

```text
[main ...] chore: create backend python project
```

---

### Task 3: Add Configuration Loading

**Files:**
- Create: `backend/app/core/config.py`

- [ ] **Step 1: Write the failing configuration test**

Create `backend/tests/test_config.py`:

```python
from app.core.config import Settings


def test_settings_read_evalforge_environment_variables(monkeypatch):
    monkeypatch.setenv("EVALFORGE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "EVALFORGE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db:5432/example",
    )
    monkeypatch.setenv("EVALFORGE_REDIS_URL", "redis://redis:6379/1")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.database_url == "postgresql+asyncpg://user:pass@db:5432/example"
    assert settings.redis_url == "redis://redis:6379/1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
uv run --directory backend pytest tests/test_config.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'app.core.config'
```

- [ ] **Step 3: Implement settings**

Create `backend/app/core/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVALFORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run the configuration test**

Run:

```powershell
uv run --directory backend pytest tests/test_config.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit configuration loading**

Run:

```powershell
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat: add backend settings"
```

Expected:

```text
[main ...] feat: add backend settings
```

---

### Task 4: Add FastAPI App Factory

**Files:**
- Create: `backend/app/main.py`
- Test: `backend/tests/test_app.py`

- [ ] **Step 1: Write the failing app factory test**

Create `backend/tests/test_app.py`:

```python
from fastapi import FastAPI

from app.main import create_app


def test_create_app_returns_fastapi_application():
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "EvalForge AI API"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
uv run --directory backend pytest tests/test_app.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'app.main'
```

- [ ] **Step 3: Implement the FastAPI entry point**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    return app


app = create_app()
```

- [ ] **Step 4: Run the app factory test**

Run:

```powershell
uv run --directory backend pytest tests/test_app.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the FastAPI app factory**

Run:

```powershell
git add backend/app/main.py backend/tests/test_app.py
git commit -m "feat: create fastapi application"
```

Expected:

```text
[main ...] feat: create fastapi application
```

---

### Task 5: Add Database and Redis Health Helpers

**Files:**
- Create: `backend/app/db/health.py`
- Create: `backend/app/core/redis.py`
- Test: `backend/tests/test_service_health_helpers.py`

- [ ] **Step 1: Write tests for failed connectivity handling**

Create `backend/tests/test_service_health_helpers.py`:

```python
import pytest

from app.core.redis import check_redis
from app.db.health import check_database


@pytest.mark.anyio
async def test_check_database_returns_false_for_invalid_database_url():
    ok = await check_database("postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid")

    assert ok is False


@pytest.mark.anyio
async def test_check_redis_returns_false_for_invalid_redis_url():
    ok = await check_redis("redis://127.0.0.1:1/0")

    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run --directory backend pytest tests/test_service_health_helpers.py -v
```

Expected:

```text
ModuleNotFoundError
```

- [ ] **Step 3: Implement PostgreSQL health helper**

Create `backend/app/db/health.py`:

```python
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def check_database(database_url: str | None = None) -> bool:
    settings = get_settings()
    engine = create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
    )

    try:
        async with asyncio.timeout(settings.health_check_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()
```

- [ ] **Step 4: Implement Redis health helper**

Create `backend/app/core/redis.py`:

```python
import asyncio

from redis.asyncio import Redis

from app.core.config import get_settings


async def check_redis(redis_url: str | None = None) -> bool:
    settings = get_settings()
    client = Redis.from_url(
        redis_url or settings.redis_url,
        decode_responses=True,
    )

    try:
        async with asyncio.timeout(settings.health_check_timeout_seconds):
            return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
```

- [ ] **Step 5: Run helper tests**

Run:

```powershell
uv run --directory backend pytest tests/test_service_health_helpers.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit health helpers**

Run:

```powershell
git add backend/app/db/health.py backend/app/core/redis.py backend/tests/test_service_health_helpers.py
git commit -m "feat: add service health helpers"
```

Expected:

```text
[main ...] feat: add service health helpers
```

---

### Task 6: Add `/healthz` API Route

**Files:**
- Create: `backend/app/api/health.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Write route tests**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.api import health as health_module
from app.main import create_app


def test_healthz_returns_ok_when_dependencies_are_reachable(monkeypatch):
    async def fake_check_database(database_url: str | None = None) -> bool:
        return True

    async def fake_check_redis(redis_url: str | None = None) -> bool:
        return True

    monkeypatch.setattr(health_module, "check_database", fake_check_database)
    monkeypatch.setattr(health_module, "check_redis", fake_check_redis)

    client = TestClient(create_app())
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api": True,
        "database": True,
        "redis": True,
    }


def test_healthz_returns_degraded_when_a_dependency_is_down(monkeypatch):
    async def fake_check_database(database_url: str | None = None) -> bool:
        return True

    async def fake_check_redis(redis_url: str | None = None) -> bool:
        return False

    monkeypatch.setattr(health_module, "check_database", fake_check_database)
    monkeypatch.setattr(health_module, "check_redis", fake_check_redis)

    client = TestClient(create_app())
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "api": True,
        "database": True,
        "redis": False,
    }
```

- [ ] **Step 2: Run route tests to verify they fail**

Run:

```powershell
uv run --directory backend pytest tests/test_health.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'app.api.health'
```

- [ ] **Step 3: Implement the health route**

Create `backend/app/api/health.py`:

```python
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.redis import check_redis
from app.db.health import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    api: bool
    database: bool
    redis: bool


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    settings = get_settings()
    database_ok, redis_ok = await asyncio.gather(
        check_database(settings.database_url),
        check_redis(settings.redis_url),
    )

    return HealthResponse(
        status="ok" if database_ok and redis_ok else "degraded",
        api=True,
        database=database_ok,
        redis=redis_ok,
    )
```

- [ ] **Step 4: Register the health route in `main.py`**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI

from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run route tests**

Run:

```powershell
uv run --directory backend pytest tests/test_health.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run all backend tests**

Run:

```powershell
uv run --directory backend pytest -v
```

Expected:

```text
6 passed
```

- [ ] **Step 7: Commit the health endpoint**

Run:

```powershell
git add backend/app/api/health.py backend/app/main.py backend/tests/test_health.py
git commit -m "feat: add backend health endpoint"
```

Expected:

```text
[main ...] feat: add backend health endpoint
```

---

### Task 7: Add Docker Compose Runtime

**Files:**
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create backend Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create Docker Compose file**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: evalforge-postgres
    environment:
      POSTGRES_DB: evalforge
      POSTGRES_USER: evalforge
      POSTGRES_PASSWORD: evalforge
    ports:
      - "5432:5432"
    volumes:
      - evalforge-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evalforge -d evalforge"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: evalforge-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build:
      context: ./backend
    container_name: evalforge-backend
    environment:
      EVALFORGE_ENVIRONMENT: docker
      EVALFORGE_DATABASE_URL: postgresql+asyncpg://evalforge:evalforge@postgres:5432/evalforge
      EVALFORGE_REDIS_URL: redis://redis:6379/0
      EVALFORGE_HEALTH_CHECK_TIMEOUT_SECONDS: "2.0"
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  evalforge-postgres-data:
```

- [ ] **Step 3: Build and start the stack**

Run:

```powershell
docker compose up --build -d
```

Expected:

```text
Container evalforge-postgres  Healthy
Container evalforge-redis     Healthy
Container evalforge-backend   Started
```

- [ ] **Step 4: Verify the health endpoint through Docker**

Run:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
```

Expected:

```text
status database redis api
------ -------- ----- ---
ok         True  True True
```

- [ ] **Step 5: Commit Docker runtime files**

Run:

```powershell
git add backend/Dockerfile docker-compose.yml
git commit -m "chore: add docker compose runtime"
```

Expected:

```text
[main ...] chore: add docker compose runtime
```

---

### Task 8: Add Developer Documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create the README**

Create `README.md`:

```markdown
# EvalForge AI

EvalForge AI is a production-style evaluation and regression testing platform for LLM and RAG applications. The project is being built as a deep fresher portfolio project focused on explainable backend systems, AI evaluation rigor, reproducible benchmarks, and interview-ready engineering tradeoffs.

## Sprint 0 Status

Sprint 0 establishes the foundation:

- FastAPI backend
- `uv` dependency management
- PostgreSQL through Docker Compose
- Redis through Docker Compose
- `/healthz` endpoint for API, database, and Redis reachability
- pytest test setup
- ruff lint and format setup

## Local Backend Setup

Install Python dependencies:

```powershell
uv sync --directory backend
```

Run tests:

```powershell
uv run --directory backend pytest -v
```

Run linting:

```powershell
uv run --directory backend ruff check .
```

Run formatting check:

```powershell
uv run --directory backend ruff format --check .
```

Start the backend locally without Docker:

```powershell
uv run --directory backend uvicorn app.main:app --reload
```

## Docker Compose

Start PostgreSQL, Redis, and the backend:

```powershell
docker compose up --build
```

Check platform health:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
```

Expected healthy response:

```json
{
  "status": "ok",
  "api": true,
  "database": true,
  "redis": true
}
```

## Sprint 0 Interview Explanation

I started EvalForge by building a reproducible backend foundation. FastAPI exposes the API, PostgreSQL stores future platform state, Redis supports future background jobs, and Docker Compose runs the stack locally. The first endpoint is `/healthz`, which checks that the API, database, and Redis are reachable before any evaluation features are added.
```

- [ ] **Step 2: Commit README**

Run:

```powershell
git add README.md
git commit -m "docs: document sprint 0 foundation"
```

Expected:

```text
[main ...] docs: document sprint 0 foundation
```

---

### Task 9: Run Final Sprint 0 Verification

**Files:**
- Modify only if verification finds a concrete issue.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
uv run --directory backend pytest -v
```

Expected:

```text
6 passed
```

- [ ] **Step 2: Run ruff lint**

Run:

```powershell
uv run --directory backend ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run ruff format check**

Run:

```powershell
uv run --directory backend ruff format --check .
```

Expected:

```text
Would reformat: 0 files
```

If the exact ruff success text differs by version, the command must exit with code 0.

- [ ] **Step 4: Rebuild Docker stack**

Run:

```powershell
docker compose up --build -d
```

Expected:

```text
evalforge-postgres healthy
evalforge-redis healthy
evalforge-backend started
```

- [ ] **Step 5: Verify health endpoint**

Run:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
```

Expected:

```text
status database redis api
------ -------- ----- ---
ok         True  True True
```

- [ ] **Step 6: Check Git status**

Run:

```powershell
git status --short
```

Expected:

```text
```

No output means the worktree is clean.

- [ ] **Step 7: Write Sprint 0 learning notes**

Create `docs/sprint-0-learning-notes.md`:

```markdown
# Sprint 0 Learning Notes

## What We Built

We built the backend foundation for EvalForge AI:

- FastAPI app entry point
- `/healthz` endpoint
- environment-based settings
- PostgreSQL health check
- Redis health check
- Docker Compose stack
- pytest and ruff setup

## How The Request Flows

1. A client calls `GET /healthz`.
2. FastAPI routes the request to `healthz()`.
3. The route loads settings.
4. The route checks PostgreSQL and Redis concurrently.
5. The route returns `ok` if both dependencies respond.
6. The route returns `degraded` if either dependency is unavailable.

## Interview Explanation

Sprint 0 gave the project a production-style base. I used FastAPI for the API layer, PostgreSQL for persistent state, Redis for future worker queues, and Docker Compose so the stack can run consistently on another machine. The health endpoint is the first integration point because it proves that the API can communicate with its infrastructure dependencies.

## Concepts To Revise

- FastAPI app factory
- Python packages and `__init__.py`
- environment variables
- Docker Compose services
- PostgreSQL vs Redis
- async health checks
- pytest monkeypatching
- ruff linting and formatting
```

- [ ] **Step 8: Commit learning notes**

Run:

```powershell
git add docs/sprint-0-learning-notes.md
git commit -m "docs: add sprint 0 learning notes"
```

Expected:

```text
[main ...] docs: add sprint 0 learning notes
```

---

## Sprint 0 Completion Definition

Sprint 0 is complete when:

- `uv sync --directory backend` succeeds.
- `uv run --directory backend pytest -v` succeeds.
- `uv run --directory backend ruff check .` succeeds.
- `uv run --directory backend ruff format --check .` succeeds.
- `docker compose up --build -d` starts PostgreSQL, Redis, and backend.
- `GET http://localhost:8000/healthz` returns `status: ok`.
- The README explains how to run the foundation.
- The learning notes explain the architecture in interview language.
