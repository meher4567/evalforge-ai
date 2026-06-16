import { BarChart3, ClipboardCheck } from "lucide-react";
import type { DashboardSnapshot } from "../api/client";
import type { TraceCase } from "../data/demo";
import { formatCost, formatLatency, formatPercent } from "../lib/format";
import { CalibrationPanel } from "./CalibrationPanel";
import { ComparisonBars } from "./ComparisonBars";
import { MetricCard } from "./MetricCard";
import { RunsTable } from "./RunsTable";
import { StatusPill } from "./StatusPill";
import { TraceInspector } from "./TraceInspector";

const filters = ["all", "token_f1_overlap", "contains_keywords", "forbidden_claim"] as const;

export type FailureFilter = (typeof filters)[number];

export function PageTitle({
  title,
  selectedVersion,
  benchmark,
  caseCount,
  meanCost,
}: {
  title: string | undefined;
  selectedVersion: string;
  benchmark: string;
  caseCount: number;
  meanCost: number;
}) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        <p>
          {selectedVersion} | {benchmark}
        </p>
      </div>
      <div className="page-title__right">
        <StatusPill status="fail" label="candidate failed" />
        <span>
          <ClipboardCheck size={16} />
          {caseCount} cases
        </span>
        <span>
          <BarChart3 size={16} />
          {formatCost(meanCost)} mean cost
        </span>
      </div>
    </div>
  );
}

export function GatePanel({ summary }: { summary: DashboardSnapshot["benchmarkSummary"] }) {
  return (
    <section className="gate-panel" aria-label="Gate verdict">
      <div>
        <h2>Gate verdict</h2>
        <p>
          {summary.caseCount} cases | {summary.totalExecutions} executions
        </p>
      </div>
      <div className="gate-panel__verdict">
        <StatusPill status="fail" label="fail" />
        <strong>Regression blocked</strong>
      </div>
      <dl className="gate-panel__numbers">
        <div>
          <dt>Elapsed</dt>
          <dd>{summary.elapsedSeconds.toFixed(2)}s</dd>
        </div>
        <div>
          <dt>Throughput</dt>
          <dd>{Math.round(summary.casesPerMinute).toLocaleString()} cases/min</dd>
        </div>
      </dl>
    </section>
  );
}

export function OverviewView({
  snapshot,
  selectedRunId,
  onSelectRun,
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
  snapshot: DashboardSnapshot;
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  selectedTraceIndex: number;
  onSelectTraceIndex: (index: number) => void;
}) {
  return (
    <div className="detail-layout overview-layout">
      <div className="dashboard-grid">
        <div className="metric-grid">
          {snapshot.metrics.map((metric) => (
            <MetricCard key={metric.key} metric={metric} />
          ))}
        </div>
        <GatePanel summary={snapshot.benchmarkSummary} />
        <ComparisonBars metrics={snapshot.metrics} />
        <RunsTable runs={snapshot.runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
      </div>
      <TraceInspector
        cases={snapshot.traceCases}
        selectedIndex={selectedTraceIndex}
        onSelectIndex={onSelectTraceIndex}
      />
    </div>
  );
}

export function RunDetailView({
  snapshot,
  selectedRunId,
  onSelectRun,
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
  snapshot: DashboardSnapshot;
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  selectedTraceIndex: number;
  onSelectTraceIndex: (index: number) => void;
}) {
  const selectedRun = snapshot.runs.find((run) => run.id === selectedRunId) ?? snapshot.runs[0];
  const completed = selectedRun.status === "partial" ? selectedRun.cases - 4 : selectedRun.cases;

  return (
    <div className="detail-layout">
      <main className="detail-main">
        <section className="panel run-summary">
          <div className="panel__header">
            <div>
              <h2>{selectedRun.id}</h2>
              <p>{selectedRun.version}</p>
            </div>
            <StatusPill status={selectedRun.status} />
          </div>
          <div className="run-stat-grid">
            <span>
              Cases <strong>{selectedRun.cases}</strong>
            </span>
            <span>
              Completed <strong>{completed}</strong>
            </span>
            <span>
              Pass rate <strong>{formatPercent(selectedRun.passRate)}</strong>
            </span>
            <span>
              p95 latency <strong>{formatLatency(selectedRun.p95LatencyMs)}</strong>
            </span>
          </div>
          <div className="progress-track" aria-label="Run progress">
            <span style={{ width: `${(completed / selectedRun.cases) * 100}%` }} />
          </div>
        </section>
        <RunsTable runs={snapshot.runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
      </main>
      <TraceInspector
        cases={snapshot.traceCases}
        selectedIndex={selectedTraceIndex}
        onSelectIndex={onSelectTraceIndex}
      />
    </div>
  );
}

export function FailureTable({
  failures,
  filter,
  onFilterChange,
  onSelectTrace,
}: {
  failures: TraceCase[];
  filter: FailureFilter;
  onFilterChange: (filter: FailureFilter) => void;
  onSelectTrace: (index: number) => void;
}) {
  const filtered = failures.filter((failure) => filter === "all" || failure.evaluator === filter);

  return (
    <section className="panel table-panel" aria-label="Failure cases">
      <div className="panel__header">
        <div>
          <h2>Failure cases</h2>
          <p>{filtered.length} visible failures after evaluator filter</p>
        </div>
        <div className="segmented-control" role="tablist" aria-label="Failure evaluator filter">
          {filters.map((item) => (
            <button
              className={filter === item ? "is-active" : ""}
              key={item}
              type="button"
              onClick={() => onFilterChange(item)}
            >
              {item === "all" ? "All" : item.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Tag</th>
              <th>Evaluator</th>
              <th>Overlap</th>
              <th>Keywords</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((failure) => {
              const originalIndex = failures.findIndex((item) => item.id === failure.id);
              return (
                <tr key={failure.id}>
                  <td>
                    <button
                      className="link-button"
                      type="button"
                      onClick={() => onSelectTrace(originalIndex)}
                    >
                      {failure.id}
                    </button>
                  </td>
                  <td>{failure.tag}</td>
                  <td>{failure.evaluator}</td>
                  <td>{failure.semanticScore.toFixed(2)}</td>
                  <td>{failure.keywordScore.toFixed(2)}</td>
                  <td>{failure.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function TagBreakdownPanel({
  rows,
}: {
  rows: DashboardSnapshot["tagBreakdown"];
}) {
  return (
    <section className="panel tag-breakdown-panel" aria-label="Tag breakdown">
      <div className="panel__header">
        <div>
          <h2>Tag breakdown</h2>
          <p>Candidate pass rate by first case tag</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tag</th>
              <th>Baseline</th>
              <th>Candidate</th>
              <th>Failed</th>
              <th>Pass rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.tag}>
                <td>{row.tag}</td>
                <td>{row.baselineCaseCount}</td>
                <td>{row.candidateCaseCount}</td>
                <td>{row.candidateFailureCount}</td>
                <td>
                  <span className="tag-pass-rate">
                    <span
                      className="tag-pass-rate__bar"
                      style={{ width: `${row.candidatePassRate * 100}%` }}
                    />
                    <strong>{formatPercent(row.candidatePassRate)}</strong>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ComparisonView({
  snapshot,
  filter,
  onFilterChange,
  onSelectTrace,
}: {
  snapshot: DashboardSnapshot;
  filter: FailureFilter;
  onFilterChange: (filter: FailureFilter) => void;
  onSelectTrace: (index: number) => void;
}) {
  return (
    <div className="comparison-layout">
      <GatePanel summary={snapshot.benchmarkSummary} />
      <ComparisonBars metrics={snapshot.metrics} />
      <TagBreakdownPanel rows={snapshot.tagBreakdown} />
      <FailureTable
        failures={snapshot.traceCases}
        filter={filter}
        onFilterChange={onFilterChange}
        onSelectTrace={onSelectTrace}
      />
    </div>
  );
}

export function TracesView({
  traceCases,
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
  traceCases: TraceCase[];
  selectedTraceIndex: number;
  onSelectTraceIndex: (index: number) => void;
}) {
  return (
    <div className="detail-layout">
      <FailureTable
        failures={traceCases}
        filter="all"
        onFilterChange={() => undefined}
        onSelectTrace={onSelectTraceIndex}
      />
      <TraceInspector
        cases={traceCases}
        selectedIndex={selectedTraceIndex}
        onSelectIndex={onSelectTraceIndex}
      />
    </div>
  );
}

export function SettingsView({ rules }: { rules: DashboardSnapshot["gateRules"] }) {
  return (
    <section className="panel settings-panel" aria-label="Gate settings">
      <div className="panel__header">
        <div>
          <h2>Gate settings</h2>
          <p>Thresholds used by the current comparison report</p>
        </div>
        <StatusPill status="fail" label="active gate" />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Direction</th>
              <th>Tolerance</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.metric}>
                <td>{rule.metric}</td>
                <td>{rule.direction === "higher" ? "Higher is better" : "Lower is better"}</td>
                <td>{rule.tolerance}</td>
                <td>
                  <StatusPill status={rule.verdict} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export { CalibrationPanel };
