# Phase 3 Execution And Comparison Design

## Goal

Phase 3 makes EvalForge end-to-end on the backend. A user can trigger a run for an app version and eval suite, persist per-case outputs, store traces, evaluate every output, and compare a baseline run against a candidate run.

## Execution Mode

This phase started with an in-process deterministic executor. The public API now supports both sync execution for tests/local demos and Celery-backed execution for Redis worker runs.

This split is intentional:

- The deterministic executor proves the platform logic before adding queue infrastructure.
- The Celery worker path proves the same run, trace, evaluator, and comparison contracts under Redis-backed execution.
- Docker Compose verified the Celery path locally on June 16, 2026 with 50-case baseline and candidate runs.

## Run Flow

1. `POST /api/runs` receives `app_version_id`, `suite_id`, and `evaluator_config_id`.
2. The executor loads the version, suite cases, evaluator config, and adapter.
3. For each case:
   - extract the input question,
   - call the adapter,
   - store the run item,
   - store the trace,
   - run configured evaluators,
   - store evaluator results.
4. The run finishes as `completed` or `partial`.

## Comparison Flow

1. `POST /api/comparisons` receives baseline and candidate run IDs.
2. The comparison service checks both runs use the same suite and are finished.
3. It computes:
   - pass rate,
   - semantic similarity mean,
   - p95 latency,
   - mean cost.
4. It reports point estimates and bootstrap confidence intervals.
5. It applies default quality, latency, and cost gates and stores a regression report.

## Statistical Note

The bootstrap implementation uses deterministic seeded resampling so local test runs are reproducible. This is not a replacement for deeper statistical validation, but it gives the project the correct measurement shape early.

## Learning Target

After this phase, the user should be able to explain:

- how a run differs from a run item,
- why traces are stored separately,
- how evaluator errors differ from app failures,
- why comparison should happen after both runs finish,
- what bootstrap confidence intervals are doing at a high level,
- how the sync and Celery paths preserve the same run, trace, evaluator, and comparison contracts.
