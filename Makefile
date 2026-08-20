.PHONY: up down build rebuild logs seed test lint format demo run-comparison benchmark clean shell shell-backend shell-db health

# ─── Docker Compose ────────────────────────────────────────────
up:
	docker compose up -d
	@echo "✅ EvalForge stack is running: http://localhost:5173 (frontend) http://localhost:8000/docs (API)"

down:
	docker compose down

build:
	docker compose build --no-cache

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

logs:
	docker compose logs -f

# ─── Data seeding ───────────────────────────────────────────────
seed:
	@echo "Seeding database with complete demo project (apps, versions, suites, cases, evaluator configs, runs, comparison)..."
	docker compose exec backend uv run python -m app.cli.seed --cases 500
	@echo "✅ Seed complete. Dashboard now has persisted comparison data."
	@echo "   Frontend: http://localhost:5173"
	@echo "   API:      http://localhost:8000/api/dashboard/latest"

seed-local:
	cd backend && uv run alembic upgrade head
	cd backend && uv run python -m app.cli.seed --cases 100
	@echo "✅ Local seed complete with 100 cases."

# ─── Test suite ─────────────────────────────────────────────────
test:
	cd backend && uv run pytest tests/ -v --tb=short

test-cov:
	cd backend && uv run pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=70

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .

format:
	cd backend && uv run ruff check --fix .
	cd backend && uv run ruff format .

# ─── Demo flow ──────────────────────────────────────────────────
demo: up seed
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  EvalForge AI — Demo Ready"
	@echo "  Frontend:  http://localhost:5173"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Health:    http://localhost:8000/healthz"
	@echo "═══════════════════════════════════════════════"
	@echo ""
	@echo "Next: open http://localhost:5173 to explore the dashboard"

# ─── Comparison run ─────────────────────────────────────────────
run-comparison:
	docker compose exec backend uv run python -m app.demo.scenario

# ─── Benchmarks ─────────────────────────────────────────────────
benchmark-throughput:
	cd backend && uv run python -m benchmarks.run_demo

benchmark-full:
	cd backend && uv run python -m benchmarks.run_demo
	cd backend && uv run python -m benchmarks.flaky_eval

# ─── Health checks ──────────────────────────────────────────────
health:
	@echo "Frontend ..." && curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 && echo " OK"
	@echo "API ......." && curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz && echo " OK"
	@echo "API Docs .." && curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs && echo " OK"
	@echo "Postgres .." && docker compose exec postgres pg_isready -U evalforge -d evalforge && echo " OK"
	@echo "Redis ....." && docker compose exec redis redis-cli ping && echo " OK"

# ─── Shell access ───────────────────────────────────────────────
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U evalforge -d evalforge

# ─── Cleanup ────────────────────────────────────────────────────
clean:
	docker compose down -v
	@echo "🧹 Removed all containers and volumes"

# ─── Full verification (pre-commit / pre-push) ──────────────────
verify:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=70
	cd frontend && npm run lint
	cd frontend && npm run test -- --run
	cd frontend && npm run build
	@echo ""
	@echo "✅ All checks passed: lint, format, backend tests, frontend tests, frontend build"

# ─── CI simulation ──────────────────────────────────────────────
ci:
	$(MAKE) lint
	$(MAKE) test
	@echo "✅ CI checks passed"
