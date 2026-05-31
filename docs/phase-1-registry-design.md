# Phase 1 Registry Design

## Goal

Phase 1 adds the persistent registry layer for EvalForge AI. This layer stores the stable project objects that every later phase depends on: applications, app versions, eval suites, eval cases, evaluator configs, runs, traces, comparison reports, and calibration labels.

## Design Choice

The production target remains PostgreSQL, but tests use SQLite through SQLAlchemy's async engine. To keep both paths reliable, IDs are stored as UUID strings and JSON fields use SQLAlchemy's portable JSON type. This keeps the code testable locally while still matching the PostgreSQL deployment shape.

## Important Correction From The Design Docs

The original technical design described immutable cases but also placed `suite_id` directly on `eval_cases`. That makes case reuse and suite membership updates awkward. Phase 1 uses an explicit `eval_suite_cases` association table instead:

- `eval_cases` stores immutable case payloads.
- `eval_suite_cases` attaches cases to suites.

This matches the design invariant that editing a case should create a new case row and update suite membership, rather than mutating historical case content.

## Phase 1 API Surface

- `POST /api/apps`
- `GET /api/apps`
- `GET /api/apps/{app_id}`
- `POST /api/apps/{app_id}/versions`
- `GET /api/apps/{app_id}/versions`
- `POST /api/apps/{app_id}/suites`
- `POST /api/suites/{suite_id}/cases/import`
- `GET /api/suites/{suite_id}/cases`
- `GET /api/suites/{suite_id}/summary`
- `POST /api/evaluator-configs`
- `GET /api/evaluator-configs`

## Learning Target

After this phase, the user should be able to explain:

- why a database model is not the same as an API schema,
- why immutable eval cases matter,
- why JSON payloads are useful for eval cases and version configs,
- how FastAPI dependencies inject a database session,
- how tests override database dependencies to use a temporary SQLite database.
