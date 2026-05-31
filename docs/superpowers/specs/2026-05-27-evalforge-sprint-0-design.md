# EvalForge AI Sprint 0 Design

## Purpose

Sprint 0 creates the foundation for EvalForge AI as a serious, explainable fresher portfolio project. The goal is not to build features quickly. The goal is to establish a clean backend-first project structure, a reproducible development environment, and a learning workflow where every file and design choice can be explained in an interview.

## Collaboration Model

We will use a guided-build workflow:

1. Explain the concept from first principles.
2. Show how it fits into EvalForge.
3. Write the real project code.
4. Walk through the important lines.
5. Run or test the result.
6. Convert the work into interview-ready explanation notes.

Explanations start beginner-friendly by default. If a concept is already familiar, the user can say "skip" or "faster" and we will compress that part.

## Sprint 0 Scope

Sprint 0 includes:

- Python backend skeleton using FastAPI.
- Python dependency management with `uv`.
- PostgreSQL and Redis services through Docker Compose.
- A backend health endpoint that verifies API, database, and Redis reachability.
- Test setup using `pytest`.
- Lint and formatting setup using `ruff`.
- Initial project documentation for local development.
- Git initialization only if the workspace is not already a Git repository and the user approves it.

Sprint 0 does not include:

- Database application models such as apps, versions, eval suites, or runs.
- Alembic migrations beyond any minimal setup needed for connectivity.
- Celery worker tasks.
- RAG app logic.
- Evaluators.
- React dashboard implementation.
- Bootstrap confidence intervals or calibration logic.

Those belong to later sprints after the foundation is working.

## Technology Decisions

Backend:

- Python 3.11+.
- FastAPI for HTTP APIs.
- Pydantic for request and response validation.
- SQLAlchemy for database connectivity when the DB layer begins.
- `uv` for dependency management and lockfile reproducibility.

Infrastructure:

- PostgreSQL for persistent relational data.
- Redis for queue/broker infrastructure, later used by Celery.
- Docker Compose for local full-stack orchestration.

Quality:

- `pytest` for automated tests.
- `ruff` for linting and formatting.

## Initial Repository Shape

The intended structure after Sprint 0 is:

```text
EvalForge-AI/
  backend/
    app/
      main.py
      api/
      core/
      db/
      models/
      schemas/
      services/
      evaluators/
      workers/
    tests/
    pyproject.toml
    uv.lock
  docs/
  docker-compose.yml
  README.md
```

The directory names are intentionally aligned with the existing project docs so future phases can grow without reorganizing the repo.

## Backend Behavior

The first backend behavior is a health endpoint:

```text
GET /healthz
```

It should return a JSON response describing whether:

- the API process is alive,
- PostgreSQL is reachable,
- Redis is reachable.

The endpoint exists for two reasons:

1. It gives us a small end-to-end integration point for Docker Compose.
2. It introduces the pattern of exposing platform health in a way the future dashboard can poll.

## Learning Outcomes

By the end of Sprint 0, the user should be able to explain:

- what FastAPI is and how a route is exposed,
- why `main.py` is the backend entry point,
- what `uv` does and why lockfiles matter,
- why PostgreSQL and Redis are separate services,
- what Docker Compose does,
- why `/healthz` matters in backend systems,
- how `pytest` verifies behavior,
- how this foundation supports later EvalForge features.

## Verification

Sprint 0 is done when:

- backend dependencies install through `uv`,
- the backend starts locally,
- `docker compose up` starts PostgreSQL, Redis, and the backend,
- `GET /healthz` returns a successful response,
- tests pass through `pytest`,
- linting passes through `ruff`,
- the user can explain the Sprint 0 architecture without reading the code.

## Interview Framing

The Sprint 0 interview explanation should sound like:

> I started by building the backend foundation in a reproducible way. FastAPI exposes the API, PostgreSQL stores platform state, Redis supports future background jobs, and Docker Compose makes the stack runnable locally. The first endpoint is `/healthz`, which checks that the API, database, and Redis are reachable. This gave me a reliable base before adding the evaluation-specific features.

