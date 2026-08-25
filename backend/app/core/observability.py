from __future__ import annotations

import logging
from collections.abc import Mapping

import sentry_sdk
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram

from app.core.config import Settings

logger = logging.getLogger("evalforge.observability")

HTTP_REQUESTS = Counter(
    "evalforge_http_requests_total",
    "HTTP requests processed by the API.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "evalforge_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "evalforge_http_requests_in_progress",
    "HTTP requests currently being processed.",
)
RUNS_CREATED = Counter(
    "evalforge_runs_created_total",
    "Evaluation runs created by execution mode.",
    ("mode",),
)


def configure_observability(app: FastAPI, settings: Settings) -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            release=app.version,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
        )

    if not settings.otel_exporter_otlp_endpoint:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": app.version,
                "deployment.environment.name": settings.environment,
            }
        )
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=_parse_headers(settings.otel_exporter_otlp_headers),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/livez,/healthz,/readyz,/metrics",
    )
    logger.info("OpenTelemetry tracing enabled for service=%s", settings.otel_service_name)


def record_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    HTTP_REQUESTS.labels(method=method, route=route, status_code=str(status_code)).inc()
    HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)


def _parse_headers(value: str | None) -> Mapping[str, str] | None:
    if not value:
        return None
    headers: dict[str, str] = {}
    for item in value.split(","):
        key, separator, header_value = item.partition("=")
        if separator and key.strip() and header_value.strip():
            headers[key.strip()] = header_value.strip()
    return headers or None
