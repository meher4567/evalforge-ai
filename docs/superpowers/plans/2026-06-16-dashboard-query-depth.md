# Dashboard Query Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the database-backed dashboard endpoint so it can select a specific comparison, paginate failed traces, and expose per-tag quality summaries.

**Architecture:** Keep the existing `/api/dashboard/latest` endpoint and extend it with optional query parameters instead of adding a parallel API. Put aggregation logic in `backend/app/services/dashboard_aggregation.py`, keeping the FastAPI router thin.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, pytest, httpx ASGI tests.

---

### Task 1: Add Dashboard Query Contract Tests

**Files:**
- Modify: `backend/tests/test_dashboard_api.py`

- [ ] **Step 1: Write failing tests**

Add tests that seed a persisted comparison, call `/api/dashboard/latest?comparison_id=...&failure_limit=1&failure_offset=1`, and assert:

```python
assert payload["tracePagination"] == {
    "total": 2,
    "limit": 1,
    "offset": 1,
    "returned": 1,
}
assert [case["id"] for case in payload["traceCases"]] == ["case-002"]
```

Add a second test that creates two comparisons and asserts `comparison_id` selects the requested report instead of the newest one.

Add a third test that asserts `tagBreakdown` contains one row per tag with baseline/candidate case counts and candidate failure count.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_api.py -q
```

Expected: FAIL because `comparison_id`, `failure_limit`, `failure_offset`, `tracePagination`, and `tagBreakdown` are not implemented.

### Task 2: Implement Dashboard Query Parameters

**Files:**
- Modify: `backend/app/api/dashboard.py`
- Modify: `backend/app/services/dashboard_aggregation.py`

- [ ] **Step 1: Add router parameters**

Extend `get_latest_dashboard_snapshot` to accept:

```python
comparison_id: str | None = None
failure_limit: int = 50
failure_offset: int = 0
```

Validate `failure_limit` is between `1` and `200`, and `failure_offset` is greater than or equal to `0` with FastAPI `Query`.

- [ ] **Step 2: Add aggregation parameters**

Extend `build_latest_dashboard_snapshot` to pass those values to helpers.

- [ ] **Step 3: Add comparison selection**

Change `_load_latest_comparison` into `_load_comparison(session, comparison_id)`:

```python
if comparison_id is not None:
    return await session.get(Comparison, comparison_id)
return await session.scalar(...)
```

- [ ] **Step 4: Add trace pagination**

Build all failed trace rows, sort them, then return the requested slice plus:

```python
{
    "total": total,
    "limit": failure_limit,
    "offset": failure_offset,
    "returned": len(page),
}
```

- [ ] **Step 5: Add per-tag breakdown**

For each candidate case, group by the first tag and return:

```python
{
    "tag": tag,
    "baselineCaseCount": baseline_count,
    "candidateCaseCount": candidate_count,
    "candidateFailureCount": failure_count,
    "candidatePassRate": round(1 - failure_count / candidate_count, 6),
}
```

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_api.py -q
```

Expected: PASS.

### Task 3: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `docs/project-status.md`
- Modify: `docs/a-grade-review.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Document the endpoint contract**

Add the query parameters and new response fields to `docs/api.md`.

- [ ] **Step 2: Update status honestly**

Move dashboard filters/pagination from "next improvement" to implemented. At the time of this dashboard plan, Docker runtime proof was still pending; that was superseded later on June 16, 2026 by a successful Compose and Celery seed smoke.

- [ ] **Step 3: Update grade**

Raise the self-grade only modestly for the dashboard-only work, because it improved dashboard depth but did not yet prove worker scale or calibration. Later Docker/Celery verification moved the current project status to `A / 9.0`; production worker throughput and calibration remain pending.

### Task 4: Full Verification

**Files:**
- No code edits.

- [ ] **Step 1: Run backend checks**

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks**

```powershell
npm run lint
npm test
npm run build
npm audit --omit=dev
```

Expected: PASS with zero production vulnerabilities.
