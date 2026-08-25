# EvalForge AI

EvalForge AI is an evaluation and regression-testing platform for RAG and LLM applications. It
runs the same test suite against baseline and candidate versions, preserves case-level evidence,
and reports statistically bounded changes in quality, latency, and cost.

![EvalForge dashboard](docs/design/phase-5-dashboard-render.png)

## Core capabilities

- Versioned application registry, evaluation suites, cases, evaluator configurations, runs, and
  trace evidence
- Adapter boundary for deterministic fixtures, local Ollama models, and allowlisted
  OpenAI-compatible providers
- Evaluators for answer quality, retrieval, faithfulness, forbidden claims, latency, and cost
- Case-paired bootstrap confidence intervals, configurable regression gates, and CI-ready reports
- PostgreSQL persistence with leased, retry-safe Celery execution through Redis
- React dashboard for comparison summaries, tag slices, failed cases, and trace inspection
- Organization-scoped sessions and API keys with owner, admin, evaluator, and viewer roles
- Migration-aware health checks, Prometheus metrics, OpenTelemetry tracing, Sentry integration, and
  documented SLOs
- Reproducible verification through backend, frontend, browser, migration, security, and full-stack
  Docker tests

## Evaluation workflow

1. Register baseline and candidate application versions.
2. Import a versioned suite of evaluation cases.
3. Select the evaluators and regression-gate policy.
4. Execute both versions synchronously or through Celery workers.
5. Compare paired case results with confidence intervals.
6. Inspect aggregate regressions and individual traces in the dashboard or CI report.

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

The backend can run evaluations synchronously for local development or dispatch case work to Celery.
Workers use delivery leases, bounded retries, database uniqueness constraints, and authoritative
progress recounting so duplicate delivery does not create duplicate evaluation results.

The dashboard reads persisted comparison snapshots and can launch a small end-to-end evaluation
through the public API. Demo data is available only when explicitly enabled with
`VITE_DEMO_MODE=true`.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic, Celery, Redis, PostgreSQL/pgvector
- Frontend: React, TypeScript, Vite, Vitest, Playwright
- Evaluation: deterministic RAG adapter, OpenAI-compatible adapter, bootstrap statistics,
  regression gates
- Infrastructure: Docker Compose, GitHub Actions

## Quick Start

Start PostgreSQL and Redis, install backend dependencies, migrate the schema, and run the API:

```bash
docker compose up -d postgres redis
uv sync --directory backend
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn app.main:app --reload
```

In another terminal, start the frontend:

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open:

```text
http://127.0.0.1:5173
```

## Docker Compose

Start the full stack:

```bash
docker compose up --build
```

Check health:

```bash
curl http://localhost:8000/readyz
```

Seed demo data through Celery worker mode:

```bash
docker compose exec backend python -m app.cli.seed --mode celery --cases 50
```

Query the latest dashboard snapshot:

```bash
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

For Groq or OpenAI, use `provider: "openai_compatible"` and set `api_key_env` to an approved
environment variable that holds the API key. Provider hosts and key-variable names are allowlisted;
configure `EVALFORGE_LLM_ALLOWED_HOSTS` and `EVALFORGE_LLM_API_KEY_ENV_ALLOWLIST` deliberately for
additional providers. Inline secrets are rejected.

Remove the local containers and their development volumes:

```bash
docker compose down -v
```

## CLI Usage

Seed a deterministic demo project in synchronous mode:

```bash
uv run --directory backend alembic upgrade head
uv run --directory backend python -m app.cli.seed --mode sync --cases 50
```

Run a baseline/candidate comparison by suite and version name:

```bash
uv run --directory backend python -m app.cli.run \
  --suite demo-suite \
  --baseline v1_baseline \
  --candidate v2_candidate \
  --sync
```

In Docker/Celery mode, omit `--sync` and let the CLI dispatch worker tasks and poll until the runs
complete.

After a comparison is computed, fetch a CI/CD gate artifact:

```bash
uv run --directory backend python -m app.cli.gate \
  --base-url http://localhost:8000 \
  --comparison-id <comparison-id> \
  --dashboard-url http://localhost:5173 \
  --json-out gate-report.json \
  --markdown-out gate-report.md
```

The gate command exits `1` when the verdict is `fail`. Add `--fail-on-warn` when warning verdicts
should block release pipelines.

## Verification

Backend:

```bash
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
uv run --directory backend pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

Frontend:

```bash
npm run lint --prefix frontend
npm test --prefix frontend
npm run test:e2e --prefix frontend
npm run build --prefix frontend
```

Docker/Celery smoke:

```bash
docker compose up --build -d
docker compose exec backend python -m app.cli.seed --mode celery --cases 50
curl http://localhost:8000/api/dashboard/latest
docker compose logs worker --tail 100
docker compose down -v
```

The repository includes a deterministic worker-throughput artifact for detecting changes in the
Docker/Celery smoke path:

```bash
python benchmarks/worker_throughput.py --cases 50 --worker-concurrency 4
```

See [benchmark interpretation](docs/benchmark-interpretation.md) before comparing results. The
fixture measures local orchestration overhead; it is not a claim about production model-provider
throughput.

## Documentation

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
- [Security policy](SECURITY.md)

## Limitations

- `semantic_similarity` is a deprecated alias for deterministic token F1 overlap; it is not a
  production semantic or judge model. Use evaluator capabilities to discover the optional embedding
  and faithfulness evaluators.
- The included adapter and benchmark are deterministic demo assets intended for reproducible
  testing.
- The committed calibration data is an author-scored synthetic fixture, not an independently
  labeled gold set.
- The committed throughput artifact measures the Docker/Celery smoke path only. Production capacity
  depends on model latency, worker sizing, and deployment hardware.

## License

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution.
