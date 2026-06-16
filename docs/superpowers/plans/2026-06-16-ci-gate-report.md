# CI Gate Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a stored EvalForge comparison into a CI/CD-ready deployment gate artifact with JSON fields, Markdown summary, and deterministic pass/fail exit behavior.

**Architecture:** Add a pure report service that accepts a comparison plus regression report and produces a stable CI report DTO. Expose it through a comparison API endpoint and a small CLI wrapper that can fetch the endpoint, write artifacts, and exit non-zero when the gate fails.

**Tech Stack:** FastAPI, Pydantic schemas, SQLAlchemy async sessions, httpx for the CLI API client, pytest, Ruff.

---

### Task 1: CI Report Service

**Files:**
- Create: `backend/app/services/ci_gate_report.py`
- Test: `backend/tests/test_ci_gate_report.py`

- [ ] **Step 1: Write failing unit tests**

Create tests that call `build_ci_gate_report()` with sample metrics and gate reasons, then assert:

```python
assert report["verdict"] == "fail"
assert report["should_fail_ci"] is True
assert report["metrics"][0]["name"] == "pass_rate"
assert "EvalForge Deployment Gate" in report["markdown"]
assert "| pass_rate |" in report["markdown"]
```

- [ ] **Step 2: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ci_gate_report.py -q
```

Expected: import failure because `app.services.ci_gate_report` does not exist.

- [ ] **Step 3: Implement service**

Implement:

```python
def build_ci_gate_report(*, comparison, report, dashboard_url=None) -> dict[str, Any]:
    ...

def render_markdown_gate_report(payload: dict[str, Any]) -> str:
    ...

def should_fail_ci(verdict: str, fail_on_warn: bool = False) -> bool:
    ...
```

- [ ] **Step 4: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ci_gate_report.py -q
```

Expected: all tests pass.

### Task 2: Comparison API Endpoint

**Files:**
- Modify: `backend/app/schemas/execution.py`
- Modify: `backend/app/api/comparisons.py`
- Test: `backend/tests/test_run_comparison_api.py`

- [ ] **Step 1: Write failing API test**

Extend the comparison integration test to call:

```text
GET /api/comparisons/{comparison_id}/ci-report?dashboard_url=http://localhost:5173
```

Assert the response contains:

```python
assert response.json()["verdict"] == "fail"
assert response.json()["should_fail_ci"] is True
assert "http://localhost:5173" in response.json()["markdown"]
```

- [ ] **Step 2: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_comparison_api.py -q -k ci_report
```

Expected: 404 because the endpoint does not exist yet.

- [ ] **Step 3: Implement endpoint**

Add `CIGateReportRead` to schemas and expose `GET /api/comparisons/{comparison_id}/ci-report`.

- [ ] **Step 4: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_comparison_api.py -q -k ci_report
```

Expected: test passes.

### Task 3: CLI Wrapper

**Files:**
- Create: `backend/app/cli/gate.py`
- Modify: `README.md`
- Test: `backend/tests/test_ci_gate_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Test exit-code logic and artifact writing through a mocked `httpx.Client`.

- [ ] **Step 2: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ci_gate_cli.py -q
```

Expected: import failure because `app.cli.gate` does not exist.

- [ ] **Step 3: Implement CLI**

Support:

```powershell
uv run --directory backend python -m app.cli.gate --base-url http://localhost:8000 --comparison-id <id> --markdown-out report.md --json-out report.json
```

Default behavior exits `1` on `fail`, exits `0` on `warn` or `pass`, and supports `--fail-on-warn`.

- [ ] **Step 4: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ci_gate_cli.py -q
```

Expected: tests pass.

### Task 4: Verification And Publish

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/project-status.md`
- Modify: `docs/a-grade-review.md`
- Modify: `docs/examples/evalforge-gate.yml`

- [ ] **Step 1: Update docs with the concrete CI gate workflow**

Document the API endpoint and CLI commands with clear production limitations.

- [ ] **Step 2: Run checks**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
cd ..
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

- [ ] **Step 3: Commit and push**

Run:

```powershell
git status --short
git add -A
git commit -m "Add CI gate report workflow"
git push
```
