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

## Prerequisites

- Python 3.11+
- `uv`
- Docker Desktop, for the full local stack

Install `uv` once if it is not already available:

```powershell
python -m pip install --user uv
```

If PowerShell cannot find `uv` after installation, add this folder to your PATH:

```powershell
$env:APPDATA\Python\Python313\Scripts
```

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
