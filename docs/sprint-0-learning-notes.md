# Sprint 0 Learning Notes

## What We Built

We built the backend foundation for EvalForge AI:

- FastAPI app entry point
- `/healthz` endpoint
- environment-based settings
- PostgreSQL health check
- Redis health check
- Docker Compose stack definition
- pytest and ruff setup

## How The Request Flows

1. A client calls `GET /healthz`.
2. FastAPI routes the request to `healthz()`.
3. The route loads settings.
4. The route checks PostgreSQL and Redis concurrently.
5. The route returns `ok` if both dependencies respond.
6. The route returns `degraded` if either dependency is unavailable.

## Interview Explanation

Sprint 0 gave the project a production-style base. I used FastAPI for the API layer, PostgreSQL for persistent state, Redis for future worker queues, and Docker Compose so the stack can run consistently on another machine. The health endpoint is the first integration point because it proves that the API can communicate with its infrastructure dependencies.

## Concepts To Revise

- FastAPI app factory
- Python packages and `__init__.py`
- environment variables
- Docker Compose services
- PostgreSQL vs Redis
- async health checks
- pytest monkeypatching
- ruff linting and formatting
