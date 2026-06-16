# API Reference

Base URL for local backend:

```text
http://127.0.0.1:8000
```

## Health

### `GET /healthz`

Returns API, database, and Redis health.

Without Docker, database and Redis may be degraded.

## Authentication

By default, local APIs are unauthenticated. If `EVALFORGE_API_KEY` is set, all `/api/*` routes require either:

```text
X-EvalForge-Api-Key: <key>
```

or:

```text
Authorization: Bearer <key>
```

`GET /healthz` remains public so infrastructure can check liveness.

## Apps

### `POST /api/apps`

```json
{
  "name": "demo-rag",
  "description": "Deterministic RAG demo"
}
```

### `GET /api/apps`

Lists registered apps.

### `GET /api/apps/{app_id}`

Returns one app.

## Versions

### `POST /api/apps/{app_id}/versions`

```json
{
  "name": "v1_baseline",
  "adapter_module": "app.adapters.demo_rag",
  "config": {
    "top_k": 1,
    "latency_ms": 120,
    "corpus": []
  }
}
```

### `GET /api/apps/{app_id}/versions`

Lists versions for one app.

## Suites And Cases

### `POST /api/apps/{app_id}/suites`

```json
{
  "name": "demo-suite"
}
```

### `POST /api/suites/{suite_id}/cases/import`

```json
{
  "cases": [
    {
      "external_id": "case-001",
      "payload": {
        "input": {
          "question": "Which Python module creates virtual environments?"
        },
        "expected_output": "Python uses venv for virtual environments.",
        "expected_facts": ["venv", "virtual environments"],
        "expected_doc_id": "venv",
        "forbidden_claims": ["quantum database"],
        "tags": ["easy", "retrieval_required"]
      }
    }
  ]
}
```

### `GET /api/suites/{suite_id}/cases`

Lists cases in a suite.

### `GET /api/suites/{suite_id}/summary`

Returns case count and tag distribution.

## Evaluator Configs

### `POST /api/evaluator-configs`

```json
{
  "name": "default-rag",
  "config": {
    "evaluators": [
      {"name": "contains_keywords", "threshold": 0.8},
      {"name": "token_f1_overlap", "threshold": 0.5},
      {"name": "embedding_similarity", "threshold": 0.65},
      {"name": "retrieval_hit_rate"},
      {"name": "forbidden_claim"},
      {"name": "latency_threshold", "threshold_ms": 200},
      {"name": "cost_threshold", "threshold_usd": 0.01}
    ]
  }
}
```

## Runs

### `POST /api/runs`

```json
{
  "app_version_id": "uuid",
  "suite_id": "uuid",
  "evaluator_config_id": "uuid"
}
```

With `EVALFORGE_RUN_MODE=sync`, the API executes in-process and returns a completed run for the deterministic demo. With `EVALFORGE_RUN_MODE=celery`, it dispatches case tasks to Celery workers and returns a running run while workers complete it.

### `GET /api/runs`

Lists runs.

### `GET /api/runs/{run_id}`

Returns run status and counters.

### `GET /api/runs/{run_id}/items`

Returns case-level run items with evaluator results.

### `GET /api/runs/{run_id}/traces/{case_id}`

Returns the trace for one case.

## Comparisons

### `POST /api/comparisons`

```json
{
  "baseline_run_id": "uuid",
  "candidate_run_id": "uuid"
}
```

Computes metrics and gate verdict.

### `GET /api/comparisons/{comparison_id}`

Returns comparison plus regression report.

### `GET /api/comparisons/{comparison_id}/gate-decision`

Returns:

```json
{
  "verdict": "fail",
  "reasons": [
    {
      "metric": "pass_rate",
      "verdict": "fail",
      "tolerance": 0.02,
      "delta_point": -1.0
    }
  ]
}
```

### `GET /api/comparisons/{comparison_id}/ci-report`

Returns a CI/CD-ready deployment gate artifact. It includes the gate verdict, a boolean `should_fail_ci`, metric rows, raw gate reasons, and a Markdown report that can be written to a GitHub step summary or PR comment.

Optional query parameters:

| Parameter | Default | Meaning |
|---|---:|---|
| `dashboard_url` | `null` | Link appended to the Markdown report |
| `fail_on_warn` | `false` | Treat `warn` verdicts as CI failures |

Example response:

```json
{
  "comparison_id": "uuid",
  "baseline_run_id": "uuid",
  "candidate_run_id": "uuid",
  "verdict": "fail",
  "should_fail_ci": true,
  "dashboard_url": "http://localhost:5173",
  "generated_at": "2026-06-16T00:00:00+00:00",
  "metrics": [
    {
      "name": "pass_rate",
      "baseline": 1.0,
      "candidate": 0.82,
      "delta": -0.18,
      "delta_ci": [-0.22, -0.11],
      "status": "fail"
    }
  ],
  "gate_reasons": [
    {
      "metric": "pass_rate",
      "verdict": "fail"
    }
  ],
  "markdown": "## EvalForge Deployment Gate\n\nGate verdict: `fail`\n"
}
```

CLI usage:

```powershell
uv run --directory backend python -m app.cli.gate `
  --base-url http://localhost:8000 `
  --comparison-id <comparison-id> `
  --json-out gate-report.json `
  --markdown-out gate-report.md
```

## Dashboard

### `GET /api/dashboard/latest`

Returns the latest computed comparison from the database in the shape consumed by the React dashboard.

Optional query parameters:

| Parameter | Default | Meaning |
|---|---:|---|
| `comparison_id` | latest computed comparison | Select a specific comparison instead of the newest one |
| `failure_limit` | `50` | Number of failed trace cases to return, from `1` to `200` |
| `failure_offset` | `0` | Offset into the failed trace list |

Additional dashboard fields:

```json
{
  "tracePagination": {
    "total": 2,
    "limit": 1,
    "offset": 1,
    "returned": 1
  },
  "tagBreakdown": [
    {
      "tag": "easy",
      "baselineCaseCount": 2,
      "candidateCaseCount": 2,
      "candidateFailureCount": 2,
      "candidatePassRate": 0.0
    }
  ]
}
```

Returns `404` when no computed comparison exists.

### `GET /api/dashboard/demo`

Returns the committed benchmark-backed demo snapshot with the same dashboard fields. This is useful when the database is empty or the frontend is being developed separately.

## Error Semantics

The current API uses FastAPI default error responses. Important status codes:

- `404`: entity or latest dashboard comparison not found
- `409`: invalid comparison state, such as comparing unfinished runs
- `422`: request validation failed
