# API Reference

Base URL for local backend:

```text
http://127.0.0.1:8000
```

## Health

### `GET /healthz`

Returns API, database, and Redis health.

Without Docker, database and Redis may be degraded.

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
      {"name": "semantic_similarity", "threshold": 0.5},
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

Current implementation executes in-process and returns a completed run for the deterministic demo.

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

## Dashboard

### `GET /api/dashboard/latest`

Returns the latest computed comparison from the database in the shape consumed by the React dashboard.

Returns `404` when no computed comparison exists.

### `GET /api/dashboard/demo`

Returns the committed benchmark-backed demo snapshot. This is useful when the database is empty or the frontend is being developed separately.

## Error Semantics

The current API uses FastAPI default error responses. Important status codes:

- `404`: entity or latest dashboard comparison not found
- `409`: invalid comparison state, such as comparing unfinished runs
- `422`: request validation failed
