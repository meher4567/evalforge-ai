# EvalForge AI Project Status

This document is the honest phase-by-phase status. It separates what is working now from what still needs to be done before claiming an A/A+ resume project.

## Current Grade

Current state: **A- for a fresher portfolio project**.

Why it is strong:

- backend domain model is real, not toy CRUD
- deterministic RAG adapter works
- evaluator engine works
- run execution persists traces and evaluator results
- comparison gates include bootstrap confidence intervals
- 500-case benchmark is measured and committed
- flaky-eval detection benchmark is measured and committed
- React dashboard is implemented, tested, and visually verified
- latest dashboard endpoint aggregates persisted comparisons from the database
- docs explain the architecture and phase decisions

Why it is not yet A/A+:

- Docker Compose was not runtime-verified on this machine because Docker is not installed
- Celery worker execution is still represented by an in-process executor
- dashboard aggregation is real for latest comparison, but does not yet support filters or pagination
- final hand-labeled calibration study is pending
- demo video is not recorded

## Phase Status

| Phase | Status | What exists |
|---|---|---|
| Phase 0: Foundation | Complete locally | FastAPI app, settings, health endpoint, pytest, ruff, Docker files for backend and frontend |
| Phase 1: Registry | Complete | Apps, versions, suites, case import/list/summary APIs |
| Phase 2: Runner | Prototype complete | Deterministic in-process run executor with persisted run items, traces, and results |
| Phase 3: Evaluators | Complete for MVP | exact match, keywords, semantic similarity, retrieval hit rate, forbidden claim, latency, cost |
| Phase 4: Regression gates | Complete for MVP | comparison service, bootstrap CIs, gate rules, regression report |
| Phase 5: Dashboard | Complete as demo UI | React/Vite dashboard, trace inspector, comparison filters, responsive screenshots, `GET /api/dashboard/latest`, `GET /api/dashboard/demo` |
| Phase 6: Advanced rigor | Partial | flaky-eval detection complete; calibration utilities and rubric exist; hand-labeling study still pending |
| Operational polish | Partial | CI workflow added; Docker runtime and demo video pending |

## What To Finish Next

### 1. Database-backed dashboard aggregation

Extend the query-driven dashboard aggregation.

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

Next improvement:

- add filters for app, suite, baseline run, and candidate run
- paginate failed cases
- expose per-tag metric breakdown
- expose evaluator error counts

### 2. Celery worker path

The current executor has the same domain shape as a worker, but it runs in-process. Add real Celery tasks only after Docker/Redis are available locally.

Required proof:

- trigger run through API
- task lands in Redis
- worker processes cases
- run status updates from running to completed

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

### 5. Docker runtime verification

When Docker Desktop is installed:

```powershell
docker compose up --build
Invoke-RestMethod http://localhost:8000/healthz
```

Expected full-stack health is `ok`. Without Docker, local API health can be `degraded` because Postgres and Redis are unavailable.

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

> Built EvalForge AI, a FastAPI and React evaluation platform for RAG regression testing that runs a deterministic 500-case benchmark, stores traces, computes quality/latency/cost metrics, and blocks failing candidates with bootstrap-CI gates.

Do not yet claim:

- production Celery throughput
- real Postgres/Redis Docker verification
- hand-labeled calibration findings
- multi-worker scale numbers

Those claims need the remaining proof above.
