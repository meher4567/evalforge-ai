from fastapi import FastAPI

from app.api.apps import router as apps_router
from app.api.evaluator_configs import router as evaluator_configs_router
from app.api.health import router as health_router
from app.api.suites import router as suites_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router)
    app.include_router(apps_router)
    app.include_router(suites_router)
    app.include_router(evaluator_configs_router)
    return app


app = create_app()
