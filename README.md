# EvalForge AI

EvalForge AI is an evaluation and regression testing platform for RAG and LLM applications. It compares a baseline app version against a candidate version, runs an evaluation suite, stores per-case traces, scores outputs with configurable evaluators, and reports quality, latency, and cost regressions.

![EvalForge dashboard](docs/design/phase-5-dashboard-render.png)

## Features

- FastAPI backend for apps, versions, suites, cases, runs, traces, comparisons, dashboard snapshots, and CI gate reports
- React/Vite dashboard for live run summaries, metric comparisons, traces, explicit demo/calibration states, and active gate policies
- PostgreSQL persistence with Redis-backed Celery worker execution
- Organization tenancy with password sessions, personal API keys, four RBAC roles, and an
  OIDC-ready external identity model
- Prometheus metrics, optional OpenTelemetry OTLP tracing, optional Sentry reporting, and defined
  availability/latency SLOs
- Deterministic RAG demo adapter for repeatable local and CI evaluation
- Configurable RAG adapter for Ollama or OpenAI-compatible chat completion providers
- Groq/OpenAI-compatible chat adapter for live smoke tests
- Evaluators for exact match, keyword coverage, token F1 overlap, embedding similarity, NLI faithfulness, retrieval hit rate, forbidden claims, latency, and cost
- Case-paired bootstrap confidence intervals and persisted configurable gate rules for regression decisions
- CI/CD deployment gate report API and CLI for JSON/Markdown artifacts
- Flaky-eval classification over repeated case scores
- Docker Compose stack with PostgreSQL, Redis, FastAPI, Celery worker, and nginx-served frontend
- GitHub Actions workflows for strict CI, dashboard E2E smoke, and Docker/Celery smoke verification

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

The backend can run evaluations synchronously for local development and through Celery workers for the Docker path. The worker executes leased, retry-safe case tasks, stores traces and evaluator results, and derives progress from authoritative item state before the Celery chord finalizes a run.

The dashboard can launch a small evaluation through the public API. It creates an app, versions, suite, cases, evaluator config, runs both versions, waits for completion, computes the comparison, and refreshes the latest dashboard snapshot.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic, Celery, Redis, PostgreSQL/pgvector
- Frontend: React, TypeScript, Vite, Vitest, Playwright
- Evaluation: deterministic RAG adapter, OpenAI-compatible adapter, bootstrap statistics, regression gates
- Infrastructure: Docker Compose, GitHub Actions

## Quick Start

Backend:

```powershell
docker compose up -d postgres redis
uv sync --directory backend
uv run --directory backend alembic upgrade head
uv run --directory backend pytest
uv run --directory backend uvicorn app.main:app --reload
```

Frontend:

```powershell
npm ci --prefix frontend
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
curl http://localhost:8000/readyz
```

Seed demo data through Celery worker mode:

```powershell
docker compose exec backend python -m app.cli.seed --mode celery --cases 50
```

Query the latest dashboard snapshot:

```powershell
curl http://localhost:8000/api/dashboard/latest
```

Run against a local Ollama model by creating an app version with `adapter_module` set to `app.adapters.llm_rag`:

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

For Groq or OpenAI, use `provider: "openai_compatible"` and set `api_key_env` to an approved environment variable that holds the API key. Provider hosts and key-variable names are allowlisted; configure `EVALFORGE_LLM_ALLOWED_HOSTS` and `EVALFORGE_LLM_API_KEY_ENV_ALLOWLIST` deliberately for additional providers. Inline secrets are rejected.

Stop and remove local volumes:

```powershell
docker compose down -v
```

## CLI Usage

Seed a deterministic demo project in synchronous mode:

```powershell
uv run --directory backend alembic upgrade head
uv run --directory backend python -m app.cli.seed --mode sync --cases 50
```

Run a baseline/candidate comparison by suite and version name:

```powershell
uv run --directory backend python -m app.cli.run `
  --suite demo-suite `
  --baseline v1_baseline `
  --candidate v2_candidate `
  --sync
```

In Docker/Celery mode, omit `--sync` and let the CLI dispatch worker tasks and poll until the runs complete.

After a comparison is computed, fetch a CI/CD gate artifact:

```powershell
uv run --directory backend python -m app.cli.gate `
  --base-url http://localhost:8000 `
  --comparison-id <comparison-id> `
  --dashboard-url http://localhost:5173 `
  --json-out gate-report.json `
  --markdown-out gate-report.md
```

The gate command exits `1` when the verdict is `fail`. Add `--fail-on-warn` when warning verdicts should block release pipelines.

## Verification

Backend:

```powershell
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
uv run --directory backend pytest --cov=app --cov-report=term-missing --cov-fail-under=70
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
docker compose exec backend python -m app.cli.seed --mode celery --cases 50
curl http://localhost:8000/api/dashboard/latest
docker compose logs worker --tail 100
docker compose down -v
```

Measured worker throughput:

```powershell
python benchmarks/worker_throughput.py --cases 50 --worker-concurrency 4
```

The current Docker/Celery smoke benchmark is recorded in [benchmarks/results/2026-06-03/worker_throughput.json](benchmarks/results/2026-06-03/worker_throughput.json). On a local Docker Desktop run, the worker path completed 50 baseline cases and 50 candidate cases with concurrency 4 in 2.017 seconds, or 2,974.71 case executions per minute. This is a deterministic demo workload measurement, not a production throughput claim.

## Documentation

- [Production launch and 90+ completion plan](docs/production-launch-and-90-plus-plan.md)
- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Evaluation metrics](docs/eval-metrics.md)
- [Authentication and tenant isolation](docs/authentication.md)
- [Operations and SLOs](docs/operations.md)
- [Load testing](docs/load-testing.md)
- [Backup and disaster recovery](docs/disaster-recovery.md)
- [Release checklist](docs/release-checklist.md)
- [Synthetic calibration fixture report](docs/calibration_report.md)
- [Calibration labeling rubric](docs/labeling_rubric.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Limitations

- `semantic_similarity` is a deprecated alias for deterministic token F1 overlap; it is not a production semantic or judge model. Use evaluator capabilities to discover the optional embedding and faithfulness evaluators.
- The included adapter and benchmark are deterministic demo assets, intended for reproducible testing.
- The committed calibration data is an author-scored synthetic fixture, not an independently labeled gold set.
- The committed throughput artifact measures the Docker/Celery smoke path only. Production capacity depends on model latency, worker sizing, and deployment hardware.

## License

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution.
