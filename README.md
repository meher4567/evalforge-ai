# EvalForge AI

EvalForge AI is an evaluation and regression testing platform for RAG and LLM applications. It compares a baseline app version against a candidate, runs an eval suite, stores per-case traces, scores outputs with multiple evaluators, and blocks regressions with quality, latency, and cost gates.

![EvalForge dashboard](docs/design/phase-5-dashboard-render.png)

## Honest Grade

Current grade: **A / 9.0 for a fresher portfolio project**.

This is not a production SaaS and not senior-level MAANG infrastructure. It is, however, a strong fresher project because it solves a real AI engineering problem with a concrete backend, measured benchmark, trace storage, regression metrics, a dashboard, CI, and honest documentation.

Read the full self-review in `docs/a-grade-review.md`.

## Current Demo Numbers

Measured on the deterministic demo benchmark committed in `benchmarks/results/2026-05-31/demo_results.json`:

- 500 eval cases
- 1000 total case executions
- 12.162 seconds elapsed
- 4933.21 cases per minute
- baseline pass rate: 100%
- candidate pass rate: 0%
- candidate token-overlap similarity: 0.284951
- gate verdict: fail

The committed benchmark is deterministic on purpose. It uses the local demo adapter so CI and interviews can reproduce the same numbers. The project also includes a real Groq-backed adapter and an optional live smoke test for proving external model execution.

Docker/Celery smoke verified on June 16, 2026:

- full Compose stack built and started with PostgreSQL, Redis, FastAPI, Celery worker, and frontend
- `/healthz` returned `ok` with database and Redis reachable
- 50-case Celery seed completed baseline 50/50 and candidate 50/50
- comparison computed and gate verdict failed the intentionally bad candidate

## What Is Implemented

- FastAPI backend with app, version, suite, evaluator config, run, trace, and comparison APIs
- SQLAlchemy domain model for registry, runs, traces, evaluator results, comparisons, and gold labels
- deterministic RAG demo adapter
- Groq/OpenAI-compatible chat adapter for real LLM smoke runs
- evaluator engine for exact match, keywords, token F1 overlap, embedding similarity, retrieval hit rate, forbidden claims, latency, and cost
- run executor that stores outputs, traces, evaluator results, and run status
- Celery dispatcher and worker task path for Redis-backed async execution
- Docker Compose-verified Celery seed smoke for the worker runtime path
- Alembic migration baseline for the database schema
- optional API-key protection for all data APIs
- bootstrap confidence intervals for comparison metrics
- gate verdicts across quality, latency, and cost
- CI/CD deployment gate report API and CLI for JSON/Markdown artifacts
- dashboard snapshot API at `GET /api/dashboard/demo`
- database-backed latest dashboard API at `GET /api/dashboard/latest`
- dashboard comparison selection, failed-case pagination, and per-tag quality breakdowns
- flaky-eval detection over repeated case scores
- React/Vite dashboard with overview, run detail, comparison, traces, calibration preview, and settings
- backend and frontend tests
- GitHub Actions CI workflow

See `docs/project-status.md` for the honest phase-by-phase status.

## Documentation Map

- `docs/a-grade-review.md`: honest grade, MAANG-level reality check, resume claims
- `docs/architecture.md`: system architecture, domain model, data flow
- `docs/api.md`: API reference with request examples
- `docs/eval-metrics.md`: evaluator logic, bootstrap CIs, gates, flakiness
- `docs/demo-walkthrough.md`: 90-second interview demo script
- `docs/learning-roadmap.md`: file-by-file study path
- `docs/interview-defense-guide.md`: questions and answer outlines

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

Run the deterministic flaky-eval benchmark:

```powershell
uv run --directory backend python ../benchmarks/flaky_eval.py
```

The committed flaky-eval result is:

```text
benchmarks/results/2026-05-31/flaky_eval_results.json
```

## Real LLM Smoke

Put a Groq key in `backend/.env`:

```env
GROQ_API_KEY=...
EVALFORGE_LLM_PROVIDER=groq
EVALFORGE_LLM_MODEL=llama-3.1-8b-instant
EVALFORGE_LLM_BASE_URL=https://api.groq.com/openai/v1
```

Run the live smoke test only when you intentionally want to spend free-tier quota:

```powershell
$env:EVALFORGE_RUN_LIVE_LLM_TESTS="1"
uv run --directory backend pytest tests/test_live_groq_integration.py -q
```

The test is skipped by default in normal CI.

## Database Migrations

Inspect the Alembic baseline:

```powershell
uv run --directory backend alembic -c alembic.ini history
```

Run migrations against the configured database:

```powershell
uv run --directory backend alembic -c alembic.ini upgrade head
```

For a real Postgres-backed API integration test, set a scratch database URL:

```powershell
$env:EVALFORGE_TEST_DATABASE_URL="postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge_test"
uv run --directory backend pytest tests/test_postgres_integration.py -q
```

## Optional API Auth

By default local APIs are open. Set `EVALFORGE_API_KEY` to require `X-EvalForge-Api-Key` or `Authorization: Bearer ...` for all `/api/*` routes. `/healthz` remains public.

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

Start PostgreSQL, Redis, the backend, Celery worker, and the frontend:

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

Run the worker smoke path through Celery:

```powershell
docker compose exec -T backend uv run python -m app.cli.seed --mode celery --cases 50
```

Expected result: both baseline and candidate runs finish with `completed=50 errored=0`, then the comparison gate fails the intentionally degraded candidate.

## CI/CD Gate Report

After a comparison is computed, CI can fetch a deployment gate artifact and fail the pipeline when the candidate regresses:

```powershell
uv run --directory backend python -m app.cli.gate `
  --base-url http://localhost:8000 `
  --comparison-id <comparison-id> `
  --dashboard-url http://localhost:5173 `
  --json-out gate-report.json `
  --markdown-out gate-report.md
```

The command exits `1` when the gate verdict is `fail`, writes machine-readable JSON, and writes a Markdown summary suitable for a GitHub step summary or PR comment. Add `--fail-on-warn` when warning verdicts should block deploys too.

## Sprint 0 Interview Explanation

I started EvalForge by building a reproducible backend foundation. FastAPI exposes the API, PostgreSQL stores future platform state, Redis supports future background jobs, and Docker Compose runs the stack locally. The first endpoint is `/healthz`, which checks that the API, database, and Redis are reachable before any evaluation features are added.

## Interview Explanation Now

EvalForge is no longer only a backend foundation. The current version can run a deterministic RAG regression benchmark, call a real Groq model through an adapter, persist traces and evaluator results, compute comparison metrics with confidence intervals, protect APIs with an optional key, migrate the schema with Alembic, execute the worker path through Docker Compose and Celery, emit a CI/CD deployment gate artifact, and show the result in a dashboard with failed-case pagination and per-tag breakdowns. The strongest interview story is the failure trace: a candidate version produces a hallucinated answer, the evaluator scores catch it, the gate fails, the CI report can block deployment, and the trace inspector shows the retrieved context and exact reason.

The next big upgrade is scale proof: capture worker throughput with multiple concurrency levels, add app/suite/run dashboard filters, add repeatable CI smoke logs for Docker, and complete the hand-labeled calibration study.
