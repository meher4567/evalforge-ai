# EvalForge AI

EvalForge AI is an evaluation and regression testing platform for RAG and LLM applications. It compares a baseline app version against a candidate, runs an eval suite, stores per-case traces, scores outputs with multiple evaluators, and blocks regressions with quality, latency, and cost gates.

![EvalForge dashboard](docs/design/phase-5-dashboard-render.png)

## Current Demo Numbers

Measured on the deterministic demo benchmark committed in `benchmarks/results/2026-05-31/demo_results.json`:

- 500 eval cases
- 1000 total case executions
- 12.162 seconds elapsed
- 4933.21 cases per minute
- baseline pass rate: 100%
- candidate pass rate: 0%
- candidate semantic similarity: 0.284951
- gate verdict: fail

The candidate is intentionally bad. It injects forbidden synthetic claims so the platform visibly catches a regression.

## What Is Implemented

- FastAPI backend with app, version, suite, evaluator config, run, trace, and comparison APIs
- SQLAlchemy domain model for registry, runs, traces, evaluator results, comparisons, and gold labels
- deterministic RAG demo adapter
- evaluator engine for exact match, keywords, semantic similarity, retrieval hit rate, forbidden claims, latency, and cost
- run executor that stores outputs, traces, evaluator results, and run status
- bootstrap confidence intervals for comparison metrics
- gate verdicts across quality, latency, and cost
- dashboard snapshot API at `GET /api/dashboard/demo`
- React/Vite dashboard with overview, run detail, comparison, traces, calibration preview, and settings
- backend and frontend tests
- GitHub Actions CI workflow

See `docs/project-status.md` for the honest phase-by-phase status.

## Prerequisites

- Python 3.11+
- `uv`
- Node.js 22+
- Docker Desktop, for the full local stack

Install `uv` once if it is not already available:

```powershell
python -m pip install --user uv
```

If PowerShell cannot find `uv` after installation, add this folder to your PATH:

```powershell
python -m site --user-base
```

On Windows, the `uv.exe` script is usually in the `Scripts` folder inside that user-base path.

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

When running the backend without PostgreSQL and Redis, `/healthz` should return `degraded`. That still proves the API is alive. The full Docker Compose stack should return `ok`.

## Local Frontend Setup

Install frontend dependencies:

```powershell
npm install --prefix frontend
```

Run frontend tests:

```powershell
npm test --prefix frontend
```

Run the frontend locally:

```powershell
npm run dev --prefix frontend
```

Open:

```text
http://127.0.0.1:5173
```

Build the frontend:

```powershell
npm run build --prefix frontend
```

## Benchmark Demo

Run the deterministic 500-case benchmark:

```powershell
uv run --directory backend python ../benchmarks/run_demo.py --cases 500
```

The script writes a JSON result under:

```text
benchmarks/results/YYYY-MM-DD/demo_results.json
```

The committed reference result is:

```text
benchmarks/results/2026-05-31/demo_results.json
```

## Full Verification

Backend:

```powershell
uv run --directory backend pytest
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
```

Frontend:

```powershell
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend
```

## Docker Compose

Start PostgreSQL, Redis, the backend, and the frontend:

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

Open the frontend:

```text
http://localhost:5173
```

## Sprint 0 Interview Explanation

I started EvalForge by building a reproducible backend foundation. FastAPI exposes the API, PostgreSQL stores future platform state, Redis supports future background jobs, and Docker Compose runs the stack locally. The first endpoint is `/healthz`, which checks that the API, database, and Redis are reachable before any evaluation features are added.

## Interview Explanation Now

EvalForge is no longer only a backend foundation. The current version can run a deterministic RAG regression benchmark, persist traces and evaluator results, compute comparison metrics with confidence intervals, and show the result in a dashboard. The strongest interview story is the failure trace: a candidate version produces a hallucinated answer, the evaluator scores catch it, the gate fails, and the trace inspector shows the retrieved context and exact reason.

The next big upgrade is replacing the in-process executor with real Celery workers, turning the dashboard snapshot into database aggregation, and completing the hand-labeled calibration study.
