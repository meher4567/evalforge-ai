import { AlertTriangle, CheckCircle2, CircleDollarSign, Gauge, Timer } from "lucide-react";
import type { MetricSummary } from "../data/demo";
import {
  formatCost,
  formatLatency,
  formatNumber,
  formatPercent,
  formatSignedPercentPoints,
} from "../lib/format";
import { StatusPill } from "./StatusPill";

function metricIcon(metric: MetricSummary) {
  if (metric.key === "pass_rate") return <CheckCircle2 aria-hidden="true" />;
  if (metric.key === "semantic_similarity") return <Gauge aria-hidden="true" />;
  if (metric.key === "p95_latency_ms") return <Timer aria-hidden="true" />;
  if (metric.key === "cost_mean_usd") return <CircleDollarSign aria-hidden="true" />;
  return <AlertTriangle aria-hidden="true" />;
}

function formatMetricValue(metric: MetricSummary, value: number) {
  if (metric.key === "pass_rate") return formatPercent(value);
  if (metric.key === "p95_latency_ms") return formatLatency(value);
  if (metric.key === "cost_mean_usd") return formatCost(value);
  return formatNumber(value, 3);
}

function formatDelta(metric: MetricSummary) {
  if (metric.key === "pass_rate") return formatSignedPercentPoints(metric.delta);
  if (metric.key === "p95_latency_ms") {
    const prefix = metric.delta >= 0 ? "+" : "";
    return `${prefix}${formatLatency(metric.delta)}`;
  }
  if (metric.key === "cost_mean_usd") return formatCost(metric.delta);
  const prefix = metric.delta >= 0 ? "+" : "";
  return `${prefix}${formatNumber(metric.delta, 3)}`;
}

export function MetricCard({ metric }: { metric: MetricSummary }) {
  return (
    <section className="metric-card" aria-label={metric.label}>
      <div className="metric-card__header">
        <span className="metric-card__icon">{metricIcon(metric)}</span>
        <span>{metric.label}</span>
        <StatusPill status={metric.status} />
      </div>
      <div className={`metric-card__value metric-card__value--${metric.status}`}>
        {formatMetricValue(metric, metric.candidate)}
      </div>
      <div className="metric-card__delta">
        Delta {formatDelta(metric)} | CI [{formatDelta({ ...metric, delta: metric.deltaCi[0] })},{" "}
        {formatDelta({ ...metric, delta: metric.deltaCi[1] })}]
      </div>
      <div className="metric-card__split">
        <span>
          Baseline <strong>{formatMetricValue(metric, metric.baseline)}</strong>
        </span>
        <span>
          Candidate <strong>{formatMetricValue(metric, metric.candidate)}</strong>
        </span>
      </div>
    </section>
  );
}
