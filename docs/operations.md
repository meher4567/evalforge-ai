# Operations, dashboards, and SLOs

## Telemetry

- `GET /metrics` exposes Prometheus-format counters, latency histograms, in-flight requests, and
  run creation totals. Set `EVALFORGE_METRICS_TOKEN` and scrape with a Bearer token.
- Set `EVALFORGE_OTEL_EXPORTER_OTLP_ENDPOINT` to export FastAPI traces over OTLP/HTTP. Optional
  comma-separated exporter headers belong in `EVALFORGE_OTEL_EXPORTER_OTLP_HEADERS`.
- Set `EVALFORGE_SENTRY_DSN` to enable exception reporting with PII collection disabled.
- All responses include `X-Request-ID`; callers may supply a safe request ID for correlation.

## Service-level objectives

For a rolling 30-day window:

- API availability: 99.9% of non-health requests return a non-5xx response.
- API latency: 95% of non-evaluation API requests complete within 750 ms.
- Run dispatch: 99% of accepted runs enter `running` or a terminal state within 60 seconds.
- Run integrity: fewer than 0.1% of run items remain past their lease without retry or terminal
  state.
- Data durability: meet the configured backup RPO and complete quarterly restore drills inside the
  four-hour RTO.

Suggested PromQL dashboard panels:

```promql
sum(rate(evalforge_http_requests_total{status_code=~"5.."}[5m]))
  / sum(rate(evalforge_http_requests_total[5m]))

histogram_quantile(0.95,
  sum by (le) (rate(evalforge_http_request_duration_seconds_bucket[5m])))
```

Page on fast burn (14.4x budget for 5 minutes and 1 hour) or slow burn (6x for 30 minutes and 6
hours). Alert separately on readiness failure, worker queue growth, PostgreSQL connection pressure,
Redis memory pressure, backup age, and stale run-item leases.
