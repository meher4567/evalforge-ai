import {
  Activity,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  FlaskConical,
  Gauge,
  GitCompare,
  HelpCircle,
  LayoutDashboard,
  RefreshCcw,
  Route,
  Settings,
} from "lucide-react";
import { useMemo, useState } from "react";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { ComparisonBars } from "./components/ComparisonBars";
import { MetricCard } from "./components/MetricCard";
import { RunsTable } from "./components/RunsTable";
import { StatusPill } from "./components/StatusPill";
import { TraceInspector } from "./components/TraceInspector";
import {
  benchmarkSummary,
  calibrationSignals,
  gateRules,
  metrics,
  runs,
  scatterPoints,
  traceCases,
  type TraceCase,
  type ViewId,
} from "./data/demo";
import { formatCost, formatLatency, formatPercent } from "./lib/format";

const navItems: Array<{ id: ViewId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "runs", label: "Runs", icon: Activity },
  { id: "comparison", label: "Comparison", icon: GitCompare },
  { id: "traces", label: "Traces", icon: Route },
  { id: "calibration", label: "Calibration", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: Settings },
];

const filters = ["all", "semantic_similarity", "contains_keywords", "forbidden_claim"] as const;

type FailureFilter = (typeof filters)[number];

function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar__selects" aria-label="Workspace filters">
        <span>Project: Demo RAG QA</span>
        <span>Dataset: demo_rag_500</span>
        <span>Branch: main</span>
      </div>
      <div className="topbar__actions">
        <span className="date-chip">May 31, 2026</span>
        <button className="icon-button" type="button" aria-label="Refresh dashboard">
          <RefreshCcw size={16} />
        </button>
      </div>
    </header>
  );
}

function Sidebar({
  activeView,
  onViewChange,
}: {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand__mark">E</span>
        <span>EvalForge AI</span>
      </div>
      <nav aria-label="Primary navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={activeView === item.id ? "nav-item nav-item--active" : "nav-item"}
              type="button"
              key={item.id}
              onClick={() => onViewChange(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-card">
        <span>Active comparison</span>
        <strong>candidate vs baseline</strong>
        <button type="button" onClick={() => onViewChange("comparison")}>
          Open comparison
        </button>
      </div>
      <div className="sidebar-footer">
        <button type="button">
          <BookOpen size={17} />
          Docs
        </button>
        <button type="button">
          <HelpCircle size={17} />
          Help
        </button>
      </div>
    </aside>
  );
}

function GatePanel() {
  return (
    <section className="gate-panel" aria-label="Gate verdict">
      <div>
        <h2>Gate verdict</h2>
        <p>{benchmarkSummary.caseCount} cases | {benchmarkSummary.totalExecutions} executions</p>
      </div>
      <div className="gate-panel__verdict">
        <StatusPill status="fail" label="fail" />
        <strong>Regression blocked</strong>
      </div>
      <dl className="gate-panel__numbers">
        <div>
          <dt>Elapsed</dt>
          <dd>{benchmarkSummary.elapsedSeconds.toFixed(2)}s</dd>
        </div>
        <div>
          <dt>Throughput</dt>
          <dd>{Math.round(benchmarkSummary.casesPerMinute).toLocaleString()} cases/min</dd>
        </div>
      </dl>
    </section>
  );
}

function OverviewView({
  selectedRunId,
  onSelectRun,
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  selectedTraceIndex: number;
  onSelectTraceIndex: (index: number) => void;
}) {
  return (
    <div className="detail-layout overview-layout">
      <div className="dashboard-grid">
        <div className="metric-grid">
          {metrics.map((metric) => (
            <MetricCard key={metric.key} metric={metric} />
          ))}
        </div>
        <GatePanel />
        <ComparisonBars metrics={metrics} />
        <RunsTable runs={runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
      </div>
      <TraceInspector
        cases={traceCases}
        selectedIndex={selectedTraceIndex}
        onSelectIndex={onSelectTraceIndex}
      />
    </div>
  );
}

function RunDetailView({
  selectedRunId,
  onSelectRun,
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  selectedTraceIndex: number;
  onSelectTraceIndex: (index: number) => void;
}) {
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0];
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
        <RunsTable runs={runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
      </main>
      <TraceInspector
        cases={traceCases}
        selectedIndex={selectedTraceIndex}
        onSelectIndex={onSelectTraceIndex}
      />
    </div>
  );
}

function FailureTable({
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
              {item === "all" ? "All" : item.replace("_", " ")}
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
              <th>Semantic</th>
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
                    <button className="link-button" type="button" onClick={() => onSelectTrace(originalIndex)}>
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

function ComparisonView({
  filter,
  onFilterChange,
  onSelectTrace,
}: {
  filter: FailureFilter;
  onFilterChange: (filter: FailureFilter) => void;
  onSelectTrace: (index: number) => void;
}) {
  return (
    <div className="comparison-layout">
      <GatePanel />
      <ComparisonBars metrics={metrics} />
      <FailureTable
        failures={traceCases}
        filter={filter}
        onFilterChange={onFilterChange}
        onSelectTrace={onSelectTrace}
      />
    </div>
  );
}

function TracesView({
  selectedTraceIndex,
  onSelectTraceIndex,
}: {
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

function SettingsView() {
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
            {gateRules.map((rule) => (
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

export function App() {
  const [activeView, setActiveView] = useState<ViewId>("overview");
  const [selectedRunId, setSelectedRunId] = useState(runs[0].id);
  const [selectedTraceIndex, setSelectedTraceIndex] = useState(0);
  const [failureFilter, setFailureFilter] = useState<FailureFilter>("all");

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? runs[0],
    [selectedRunId],
  );

  function selectRun(runId: string) {
    setSelectedRunId(runId);
    setActiveView("runs");
  }

  function selectTrace(index: number) {
    setSelectedTraceIndex(index);
    setActiveView("traces");
  }

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />
      <div className="workspace">
        <TopBar />
        <main className="workspace-main">
          <div className="page-title">
            <div>
              <h1>{activeView === "runs" ? "Run detail" : navItems.find((item) => item.id === activeView)?.label}</h1>
              <p>
                {selectedRun.version} | {benchmarkSummary.benchmark}
              </p>
            </div>
            <div className="page-title__right">
              <StatusPill status="fail" label="candidate failed" />
              <span>
                <ClipboardCheck size={16} />
                {benchmarkSummary.caseCount} cases
              </span>
              <span>
                <BarChart3 size={16} />
                {formatCost(metrics[3].candidate)} mean cost
              </span>
            </div>
          </div>

          {activeView === "overview" && (
            <OverviewView
              selectedRunId={selectedRunId}
              onSelectRun={selectRun}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
            />
          )}
          {activeView === "runs" && (
            <RunDetailView
              selectedRunId={selectedRunId}
              onSelectRun={selectRun}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
            />
          )}
          {activeView === "comparison" && (
            <ComparisonView
              filter={failureFilter}
              onFilterChange={setFailureFilter}
              onSelectTrace={selectTrace}
            />
          )}
          {activeView === "traces" && (
            <TracesView selectedTraceIndex={selectedTraceIndex} onSelectTraceIndex={setSelectedTraceIndex} />
          )}
          {activeView === "calibration" && <CalibrationPanel signals={calibrationSignals} points={scatterPoints} />}
          {activeView === "settings" && <SettingsView />}
        </main>
      </div>
    </div>
  );
}
