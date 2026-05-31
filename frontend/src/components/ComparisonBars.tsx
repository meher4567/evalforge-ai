import type { MetricSummary } from "../data/demo";
import { formatCost, formatLatency, formatNumber, formatPercent } from "../lib/format";
import { StatusPill } from "./StatusPill";

function formatMetric(metric: MetricSummary, value: number): string {
  if (metric.key === "pass_rate") return formatPercent(value);
  if (metric.key === "p95_latency_ms") return formatLatency(value);
  if (metric.key === "cost_mean_usd") return formatCost(value);
  return formatNumber(value, 3);
}

function barWidth(metric: MetricSummary, value: number): string {
  const max = Math.max(metric.baseline, metric.candidate, metric.tolerance, 0.000001);
  const scaled = metric.key === "cost_mean_usd" ? 100 : Math.max(8, (value / max) * 100);
  return `${Math.min(scaled, 100)}%`;
}

export function ComparisonBars({ metrics }: { metrics: MetricSummary[] }) {
  return (
    <section className="panel comparison-panel" aria-label="Comparison summary">
      <div className="panel__header">
        <div>
          <h2>Comparison summary</h2>
          <p>Baseline v1 against injected-regression candidate</p>
        </div>
        <StatusPill status="fail" label="gate fail" />
      </div>

      <div className="comparison-bars">
        {metrics.map((metric) => (
          <div className="comparison-row" key={metric.key}>
            <div className="comparison-row__label">
              <strong>{metric.shortLabel}</strong>
              <span>{metric.direction === "higher" ? "higher is better" : "lower is better"}</span>
            </div>
            <div className="comparison-row__bars">
              <div className="bar-track">
                <span
                  className="bar-track__fill bar-track__fill--baseline"
                  style={{ width: barWidth(metric, metric.baseline) }}
                />
              </div>
              <div className="bar-track">
                <span
                  className={`bar-track__fill bar-track__fill--${metric.status}`}
                  style={{ width: barWidth(metric, metric.candidate) }}
                />
              </div>
            </div>
            <div className="comparison-row__values">
              <span>Base {formatMetric(metric, metric.baseline)}</span>
              <span>Cand {formatMetric(metric, metric.candidate)}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
