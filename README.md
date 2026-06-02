# EvalForge AI

EvalForge AI is an evaluation and regression testing platform for RAG and LLM applications. It compares a baseline app version against a candidate version, runs an evaluation suite, stores per-case traces, scores outputs with configurable evaluators, and reports quality, latency, and cost regressions.

![EvalForge dashboard](docs/design/phase-5-dashboard-render.png)

## Features

- FastAPI backend for apps, versions, suites, cases, runs, traces, comparisons, and dashboard snapshots
- React/Vite dashboard for run summaries, metric comparisons, traces, calibration preview, and settings
- PostgreSQL persistence with Redis-backed Celery worker execution
- Deterministic RAG demo adapter for repeatable local and CI evaluation
- Configurable RAG adapter for Ollama or OpenAI-compatible chat completion providers
- Evaluators for exact match, keyword coverage, semantic similarity, retrieval hit rate, forbidden claims, latency, and cost
- Bootstrap confidence intervals and configurable gate rules for regression decisions
- Flaky-eval classification over repeated case scores
- Docker Compose stack with PostgreSQL, Redis, FastAPI, Celery worker, and nginx-served frontend
- GitHub Actions workflows for strict CI and Docker/Celery smoke verification

## Architecture

```text
React dashboard
      |
      v
FastAPI backend  ---> PostgreSQL
      |
      v
Redis broker  ---> Celery worker
      |
      v
App adapter + evaluator engine
```

The backend can run evaluations synchronously for local development and through Celery workers for a production-like Docker path. The worker executes individual eval cases, stores traces and evaluator results, and updates run status when the Celery chord completes.

The dashboard can launch a small evaluation through the public API. It creates an app, versions,
suite, cases, evaluator config, runs both versions, waits for completion, computes the comparison,
and refreshes the latest dashboard snapshot.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic, Celery, Redis, PostgreSQL/pgvector
- Frontend: React, TypeScript, Vite, Vitest
- Evaluation: deterministic RAG adapter, bootstrap statistics, regression gates
- Infrastructure: Docker Compose, GitHub Actions

## Quick Start

Backend:

```powershell
uv sync --directory backend
uv run --directory backend pytest
uv run --directory backend uvicorn app.main:app --reload
```

Frontend:

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

Open:

```text
http://127.0.0.1:5173
```

## Docker Compose

Start the full stack:

```powershell
docker compose up --build
```

Check health:

```powershell
curl http://localhost:8000/healthz
```

Seed demo data through Celery worker mode:

```powershell
docker compose exec backend uv run python -m app.cli.seed --mode celery --cases 50
```

Query the latest dashboard snapshot:

```powershell
curl http://localhost:8000/api/dashboard/latest
```

Run against a local Ollama model by creating an app version with `adapter_module` set to
`app.adapters.llm_rag`:

```json
{
  "name": "ollama-baseline",
  "adapter_module": "app.adapters.llm_rag",
  "config": {
    "provider": "ollama",
    "base_url": "http://host.docker.internal:11434",
    "model": "llama3.2:3b",
    "top_k": 3,
    "corpus": [
      {
        "doc_id": "python-venv",
        "text": "The venv module creates lightweight Python virtual environments."
      }
    ]
  }
}
```

For Groq, OpenAI, or another OpenAI-compatible endpoint, use
`provider: "openai_compatible"` and set `api_key_env` to the environment variable that holds the
API key.

Stop and remove local volumes:

```powershell
docker compose down -v
```

## CLI Usage

Seed a deterministic demo project in synchronous mode:

```powershell
uv run --directory backend python -m app.cli.seed --mode sync --cases 50
```

Run a baseline/candidate comparison:

```powershell
uv run --directory backend python -m app.cli.run `
  --baseline-version <baseline_version_id> `
  --candidate-version <candidate_version_id> `
  --suite <suite_id> `
  --evaluator-config <evaluator_config_id> `
  --gate-rule <gate_rule_id> `
  --sync
```

In Docker/Celery mode, omit `--sync` and let the CLI dispatch worker tasks and poll until the runs complete.

## Verification

Backend:

```powershell
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
uv run --directory backend pytest
```

Frontend:

```powershell
npm run lint --prefix frontend
npm test --prefix frontend
npm run test:e2e --prefix frontend
npm run build --prefix frontend
```

Docker/Celery smoke:

```powershell
docker compose up --build -d
docker compose exec backend uv run python -m app.cli.seed --mode celery --cases 50
curl http://localhost:8000/api/dashboard/latest
docker compose logs worker --tail 100
docker compose down -v
```

Measured worker throughput:

```powershell
python benchmarks/worker_throughput.py --cases 50 --worker-concurrency 4
```

The current Docker/Celery smoke benchmark is recorded in
[benchmarks/results/2026-06-03/worker_throughput.json](benchmarks/results/2026-06-03/worker_throughput.json).
On a local Docker Desktop run, the worker path completed 50 baseline cases and 50 candidate
cases with concurrency 4 in 2.017 seconds, or 2,974.71 case executions per minute. This is a
deterministic demo workload measurement, not a production throughput claim.

## Documentation

- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Evaluation metrics](docs/eval-metrics.md)
- [Calibration labeling rubric](docs/labeling_rubric.md)

## Limitations

- The default semantic similarity evaluator is deterministic and lightweight; it is not a replacement for a production embedding or judge model.
- The included adapter and benchmark are deterministic demo assets, intended for reproducible testing.
- The committed throughput artifact measures the Docker/Celery smoke path only. Production capacity depends on model latency, worker sizing, and deployment hardware.
