from fastapi import Depends, FastAPI

from app.api.apps import router as apps_router
from app.api.comparisons import router as comparisons_router
from app.api.dashboard import router as dashboard_router
from app.api.evaluator_configs import router as evaluator_configs_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.api.suites import router as suites_router
from app.core.auth import require_api_key


def create_app() -> FastAPI:
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router)
    protected = [Depends(require_api_key)]
    app.include_router(apps_router, dependencies=protected)
    app.include_router(suites_router, dependencies=protected)
    app.include_router(evaluator_configs_router, dependencies=protected)
    app.include_router(runs_router, dependencies=protected)
    app.include_router(comparisons_router, dependencies=protected)
    app.include_router(dashboard_router, dependencies=protected)
    return app


app = create_app()
