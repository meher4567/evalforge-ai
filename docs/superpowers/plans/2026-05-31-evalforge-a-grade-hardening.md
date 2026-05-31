# EvalForge A-Grade Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise EvalForge from a strong demo project to an honestly defensible A-grade fresher portfolio project.

**Architecture:** Add a database-backed dashboard aggregation endpoint, prefer that endpoint from the frontend, and upgrade documentation around architecture, API contracts, metrics, demo narrative, grading, and learning path. Keep unimplemented production features explicitly marked as gaps.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest, React, Vite, Vitest, Markdown documentation.

---

### Task 1: Database-Backed Dashboard Snapshot

**Files:**
- Modify: `backend/tests/test_dashboard_api.py`
- Create: `backend/app/services/dashboard_aggregation.py`
- Modify: `backend/app/api/dashboard.py`

- [x] **Step 1: Write failing tests**

Add tests for:

- `GET /api/dashboard/latest` returns `404` when no comparison exists.
- `GET /api/dashboard/latest` returns latest persisted comparison metrics, run rows, and failed trace cases after a baseline/candidate comparison is created.

- [x] **Step 2: Verify tests fail**

Run:

```powershell
uv run --directory backend pytest tests/test_dashboard_api.py
```

Expected initial result: endpoint returns default `404 Not Found`.

- [x] **Step 3: Implement aggregation**

Create `build_latest_dashboard_snapshot(session)` that loads:

- latest computed comparison
- regression report
- baseline and candidate runs
- app version names
- failed candidate run items
- traces and retrieved chunks
- gate rule verdicts

- [x] **Step 4: Verify tests pass**

Run:

```powershell
uv run --directory backend pytest tests/test_dashboard_api.py
```

Expected: all dashboard API tests pass.

### Task 2: Frontend API Preference Order

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.test.tsx`
- Create: `frontend/src/api/client.test.ts`

- [x] **Step 1: Write failing test**

Update hydration test to expect `/api/dashboard/latest`.

- [x] **Step 2: Verify test fails**

Run:

```powershell
npm test -- src/App.test.tsx
```

Expected: fetch was called with `/api/dashboard/demo`, not `/api/dashboard/latest`.

- [x] **Step 3: Implement fallback order**

Make client try:

1. `/api/dashboard/latest`
2. `/api/dashboard/demo`
3. local static snapshot

- [x] **Step 4: Verify test passes**

Run:

```powershell
npm test -- src/App.test.tsx
```

Expected: all frontend tests pass.

- [x] **Step 5: Add focused client fallback tests**

Verify:

- latest endpoint is tried first
- demo endpoint is used when latest is unavailable
- local demo data is used when API responses are not JSON

### Task 3: A-Grade Documentation

**Files:**
- Create: `docs/a-grade-review.md`
- Create: `docs/architecture.md`
- Create: `docs/api.md`
- Create: `docs/eval-metrics.md`
- Create: `docs/demo-walkthrough.md`
- Create: `docs/learning-roadmap.md`
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/interview-defense-guide.md`

- [x] **Step 1: Add honest grade review**

Document current grade as A- for fresher portfolio, not A+ or production.

- [x] **Step 2: Add architecture guide**

Document layers, flow, domain model, dashboard data flow, and scaling path.

- [x] **Step 3: Add API guide**

Document core local endpoints and example request bodies.

- [x] **Step 4: Add metrics guide**

Document evaluator behavior, confidence intervals, gate logic, flakiness, and calibration.

- [x] **Step 5: Add demo and learning guides**

Add a 90-second demo script and file-by-file learning roadmap.

### Task 4: Verification

**Files:** no source changes expected.

- [x] **Step 1: Run backend tests**

```powershell
uv run --directory backend pytest
```

Observed result: `27 passed`.

- [x] **Step 2: Run backend lint and format checks**

```powershell
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
```

Observed result: Ruff check passed; `58 files already formatted`.

- [x] **Step 3: Run frontend checks**

```powershell
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend
```

Observed result: typecheck passed; `8 passed`; production build passed; `0 vulnerabilities`.

- [x] **Step 4: Smoke-test dashboard endpoint**

Start backend on an unused port and call:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/dashboard/latest
```

If the database is empty, expect `404`. In tests with seeded data, expect `200`.

Observed result: `/api/dashboard/demo` returned `200` with 500 cases and gate `fail`; `/api/dashboard/latest` returned `404` against an empty smoke database. Browser smoke at `http://127.0.0.1:5173` rendered the dashboard with 0 console errors.

- [ ] **Step 5: Commit**

```powershell
git add .
git commit -m "feat: harden dashboard aggregation and docs"
```
