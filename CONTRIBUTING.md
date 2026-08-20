# Contributing

## Local setup

1. Install Python 3.11+, Node 22+, Docker, and `uv`.
2. Copy `backend/.env.example` to `backend/.env` and keep secrets out of Git.
3. Start PostgreSQL and Redis, then apply the schema:

   ```bash
   docker compose up -d postgres redis
   uv sync --directory backend
   uv run --directory backend alembic upgrade head
   npm ci --prefix frontend
   ```

4. Run the API and frontend in separate terminals. The Vite development server proxies `/api` to `127.0.0.1:8000`.

## Quality gate

Run `make verify` before opening a pull request. Schema changes require a new forward and backward Alembic migration. Behavior changes require tests at the smallest useful layer; production integration changes should also update the Docker smoke workflow.

Never commit credentials, copied customer prompts, or model outputs containing sensitive data. Use deterministic fixtures for tests and clearly label synthetic benchmarks and calibration data.

## Pull requests

Keep changes focused, explain operational risk and rollback, and document new environment variables or API behavior. CI must pass backend lint/format/coverage, frontend type-check/tests/build, dependency audits, CodeQL, and the applicable Docker smoke test.
