from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.apps import router as apps_router
from app.api.auth import router as auth_router
from app.api.comparisons import router as comparisons_router
from app.api.dashboard import router as dashboard_router
from app.api.evaluator_configs import router as evaluator_configs_router
from app.api.evaluators import router as evaluators_router
from app.api.gate_rules import router as gate_rules_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.organizations import router as organizations_router
from app.api.runs import router as runs_router
from app.api.suites import router as suites_router
from app.core.config import get_settings
from app.core.logging import RequestLogger
from app.core.observability import (
    HTTP_REQUESTS_IN_PROGRESS,
    configure_observability,
    record_http_request,
)


def create_app() -> FastAPI:
    settings = get_settings()
    expose_docs = settings.environment.lower() not in {"production", "prod"}
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-EvalForge-API-Key"],
            expose_headers=["X-Request-ID"],
        )
    allowed_hosts = [host.strip() for host in settings.allowed_hosts.split(",") if host.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if 0 < len(supplied_request_id) <= 128
            and all(character.isalnum() or character in "-_." for character in supplied_request_id)
            else str(uuid4())
        )
        request_logger = RequestLogger(
            request.method, request.url.path, extra={"request_id": request_id}
        )
        started_at = perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        finally:
            request_logger.complete(status_code)
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            record_http_request(
                method=request.method,
                route=route_path,
                status_code=status_code,
                duration_seconds=perf_counter() - started_at,
            )
            HTTP_REQUESTS_IN_PROGRESS.dec()

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(auth_router)
    app.include_router(organizations_router)
    app.include_router(apps_router)
    app.include_router(suites_router)
    app.include_router(evaluator_configs_router)
    app.include_router(evaluators_router)
    app.include_router(gate_rules_router)
    app.include_router(runs_router)
    app.include_router(comparisons_router)
    app.include_router(dashboard_router)
    configure_observability(app, settings)
    return app


app = create_app()
