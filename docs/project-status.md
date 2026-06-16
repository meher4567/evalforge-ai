# EvalForge AI Project Status

This document is the honest phase-by-phase status. It separates what is working now from what still needs to be done before claiming an A/A+ resume project.

## Current Grade

Current state: **A / 9.0 for a fresher portfolio project**.

Why it is strong:

- backend domain model is real, not toy CRUD
- deterministic RAG adapter works
- evaluator engine works
- run execution persists traces and evaluator results
- comparison gates include bootstrap confidence intervals
- 500-case benchmark is measured and committed
- flaky-eval detection benchmark is measured and committed
- Groq chat adapter is implemented and live-smoke tested behind an explicit flag
- Alembic baseline migration exists
- optional API-key protection exists for `/api/*`
- Celery worker service exists in Docker Compose
- Docker Compose runtime was verified locally on June 16, 2026 with PostgreSQL, Redis, FastAPI, Celery worker, and frontend
- Celery seed smoke completed 50/50 baseline cases and 50/50 candidate cases, then computed the comparison gate
- React dashboard is implemented, tested, and visually verified
- latest dashboard endpoint aggregates persisted comparisons from the database
- latest dashboard endpoint supports explicit comparison selection, failed-case pagination, and per-tag quality breakdowns
- docs explain the architecture and phase decisions

Why it is not yet A+:

- multi-worker Celery throughput at 1/2/4/8 workers is not measured yet
- dashboard aggregation is real for persisted comparisons, but app/suite/run filters are still pending
- final hand-labeled calibration study is pending
- demo video is not recorded

## Phase Status

| Phase | Status | What exists |
|---|---|---|
| Phase 0: Foundation | Complete locally | FastAPI app, settings, health endpoint, pytest, ruff, Docker files for backend and frontend |
| Phase 1: Registry | Complete | Apps, versions, suites, case import/list/summary APIs |
| Phase 2: Runner | Complete for MVP | In-process executor plus Celery dispatcher/worker task path with persisted run items, traces, and results |
| Phase 3: Evaluators | Complete for MVP | exact match, keywords, token F1 overlap, embedding similarity, retrieval hit rate, forbidden claim, latency, cost |
| Phase 4: Regression gates | Complete for MVP | comparison service, bootstrap CIs, gate rules, regression report |
| Phase 5: Dashboard | Complete as demo UI | React/Vite dashboard, trace inspector, comparison filters, tag breakdowns, failed-case pagination, `GET /api/dashboard/latest`, `GET /api/dashboard/demo` |
| Phase 6: Advanced rigor | Partial | flaky-eval detection complete; calibration utilities and rubric exist; hand-labeling study still pending |
| Operational polish | Partial | CI workflow added; Docker runtime verified locally; multi-worker throughput, CI Docker smoke, and demo video pending |

## What To Finish Next

### 1. Database-backed dashboard aggregation

Extend the query-driven dashboard aggregation beyond the comparison-level view.

Current endpoint:

```text
GET /api/dashboard/latest
GET /api/dashboard/demo
```

The latest endpoint already returns:

- benchmark summary
- metrics
- runs
- failure cases
- trace details
- gate rules
- failed-case pagination metadata
- per-tag candidate failure breakdown

Next improvement:

- add filters for app, suite, baseline run, and candidate run
- expose evaluator error counts
- expose deeper per-tag metric deltas, not just candidate failure rates

### 2. Celery worker runtime proof

Completed locally on June 16, 2026.

Verified proof:

- trigger run through API
- task lands in Redis
- worker processes cases
- run status updates from running to completed
- baseline run finished `completed=50 errored=0`
- candidate run finished `completed=50 errored=0`
- comparison gate computed and failed the intentionally degraded candidate

Next worker proof:

- record throughput with 1, 2, 4, and 8 worker processes
- add a repeatable CI Docker smoke job or published logs

### 3. Real repeated-run flakiness benchmark

The current flaky-eval benchmark uses synthetic repeated scores. Next, run real adapter executions:

```powershell
uv run --directory backend python ../benchmarks/flaky_eval.py
```

Then extend the script to sample real tagged cases and execute each case `N=5` times.

### 4. Calibration gold set

Complete the hand-labeled calibration study:

- choose 50 cases
- label outputs using `docs/labeling_rubric.md`
- compute Pearson, Spearman, confusion matrices
- write one named finding in `docs/calibration_findings.md`

Do not put calibration numbers on the resume until this is done.

### 5. Reproduce Docker runtime verification

With Docker Desktop running:

```powershell
docker compose up --build
Invoke-RestMethod http://localhost:8000/healthz
docker compose exec -T backend uv run python -m app.cli.seed --mode celery --cases 50
```

Expected full-stack health is `ok`. The Celery seed should complete both 50-case runs with no errored cases, then compute the comparison.

### 6. Demo video

Record a short demo:

1. Open dashboard.
2. Show gate fail.
3. Open comparison.
4. Filter failure table.
5. Open trace inspector.
6. Explain why the candidate failed.

Keep it under 90 seconds.

## Resume Readiness

Safe resume bullet today:

> Built EvalForge AI, a FastAPI and React evaluation platform for RAG/LLM regression testing with persisted traces, Groq-backed real-model smoke tests, token and embedding evaluators, Alembic migrations, Celery worker dispatch, and bootstrap-CI quality/latency/cost gates.

Do not yet claim:

- production Celery throughput numbers
- hand-labeled calibration findings
- multi-worker scale numbers

Those claims need the remaining proof above.
