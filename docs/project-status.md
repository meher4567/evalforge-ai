# Project Status

This document summarizes the current implementation state and the remaining work needed before operating EvalForge as a shared service.

## Implemented

- FastAPI backend with registry, run, trace, comparison, dashboard, and health APIs.
- SQLAlchemy domain model for apps, versions, suites, cases, runs, traces, evaluator results, comparisons, gate rules, and gold labels.
- Deterministic RAG adapter for reproducible local and CI runs.
- Groq/OpenAI-compatible chat adapter behind explicit configuration.
- Evaluator engine for exact match, keyword coverage, token F1 overlap, embedding similarity, retrieval hit rate, forbidden claims, latency, and cost.
- Run execution with persisted outputs, traces, evaluator results, run counters, and terminal run state.
- Redis-backed Celery worker execution through Docker Compose.
- Alembic baseline migration.
- Optional API-key protection for `/api/*`.
- Bootstrap confidence intervals and configurable quality, latency, and cost gates.
- CI/CD gate report endpoint and CLI that emit JSON/Markdown artifacts and deterministic blocking exit codes.
- React/Vite dashboard with comparison selection, failed-case pagination, per-tag breakdowns, trace inspection, and local fallback data.
- Calibration utilities, labeling rubric, and preliminary synthetic calibration report.
- Backend and frontend test suites.

## Verified Locally

| Area | Evidence |
|---|---|
| Backend quality | Ruff lint/format and full pytest suite |
| Frontend quality | TypeScript lint, Vitest, production build, npm audit |
| Docker runtime | Compose stack with PostgreSQL, Redis, FastAPI, Celery worker, and frontend |
| Worker execution | 50-case Celery seed completed baseline and candidate runs with zero errored cases |
| Gate report workflow | CLI fetched a live comparison report, wrote JSON/Markdown artifacts, and returned exit code `1` for a failed gate |

## Current Endpoints

```text
GET  /healthz
POST /api/apps
POST /api/apps/{app_id}/versions
POST /api/apps/{app_id}/suites
POST /api/suites/{suite_id}/cases/import
POST /api/evaluator-configs
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/items
GET  /api/runs/{run_id}/traces/{case_id}
POST /api/comparisons
GET  /api/comparisons/{comparison_id}
GET  /api/comparisons/{comparison_id}/gate-decision
GET  /api/comparisons/{comparison_id}/ci-report
GET  /api/dashboard/latest
GET  /api/dashboard/demo
```

## Remaining Work

| Area | Next step |
|---|---|
| Worker scale | Measure throughput with 1, 2, 4, and 8 worker processes and publish the methodology. |
| Dashboard filters | Add app, suite, baseline run, and candidate run filters to `GET /api/dashboard/latest`. |
| Calibration | Complete a hand-labeled gold set and publish correlation/confusion-matrix results. |
| CI evidence | Add a repeatable Docker smoke workflow that publishes logs and gate artifacts. |
| Deployment | Provide a hosted deployment profile with persistent Postgres, Redis, secrets, and backups. |
| Observability | Add structured request IDs, worker metrics, and error dashboards. |

## Reproduce Docker Runtime Verification

```powershell
docker compose up --build
Invoke-RestMethod http://localhost:8000/healthz
docker compose exec -T backend uv run python -m app.cli.seed --mode celery --cases 50
```

Expected health status is `ok`. The Celery seed should complete both 50-case runs with no errored cases and compute the comparison gate.

## CI Gate Report

```powershell
uv run --directory backend python -m app.cli.gate `
  --base-url http://localhost:8000 `
  --comparison-id <comparison-id> `
  --dashboard-url http://localhost:5173 `
  --json-out gate-report.json `
  --markdown-out gate-report.md
```

The command exits `1` when the gate verdict is `fail`. Add `--fail-on-warn` when warning verdicts should block release pipelines.
