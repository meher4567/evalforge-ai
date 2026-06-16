import {
  Activity,
  BookOpen,
  FlaskConical,
  GitCompare,
  HelpCircle,
  LayoutDashboard,
  RefreshCcw,
  Route,
  Settings,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { loadDashboardSnapshot, type DashboardSnapshot } from "./api/client";
import {
  CalibrationPanel,
  ComparisonView,
  type FailureFilter,
  OverviewView,
  PageTitle,
  RunDetailView,
  SettingsView,
  TracesView,
} from "./components/DashboardViews";
import {
  benchmarkSummary,
  calibrationSignals,
  gateRules,
  metrics,
  runs,
  scatterPoints,
  tagBreakdown,
  traceCases,
  tracePagination,
  type ViewId,
} from "./data/demo";

const fallbackSnapshot: DashboardSnapshot = {
  benchmarkSummary,
  metrics,
  runs,
  traceCases,
  tracePagination,
  tagBreakdown,
  gateRules,
};

const navItems: Array<{ id: ViewId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "runs", label: "Runs", icon: Activity },
  { id: "comparison", label: "Comparison", icon: GitCompare },
  { id: "traces", label: "Traces", icon: Route },
  { id: "calibration", label: "Calibration", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: Settings },
];

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
              aria-label={item.label}
              title={item.label}
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

export function App() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(fallbackSnapshot);
  const [activeView, setActiveView] = useState<ViewId>("overview");
  const [selectedRunId, setSelectedRunId] = useState(fallbackSnapshot.runs[0].id);
  const [selectedTraceIndex, setSelectedTraceIndex] = useState(0);
  const [failureFilter, setFailureFilter] = useState<FailureFilter>("all");

  useEffect(() => {
    let isMounted = true;

    loadDashboardSnapshot().then((loadedSnapshot) => {
      if (isMounted) {
        setSnapshot({
          ...fallbackSnapshot,
          ...loadedSnapshot,
          gateRules: loadedSnapshot.gateRules ?? fallbackSnapshot.gateRules,
        });
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedRun = useMemo(
    () => snapshot.runs.find((run) => run.id === selectedRunId) ?? snapshot.runs[0],
    [selectedRunId, snapshot.runs],
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
          <PageTitle
            title={activeView === "runs" ? "Run detail" : navItems.find((item) => item.id === activeView)?.label}
            selectedVersion={selectedRun.version}
            benchmark={snapshot.benchmarkSummary.benchmark}
            caseCount={snapshot.benchmarkSummary.caseCount}
            meanCost={snapshot.metrics[3].candidate}
          />

          {activeView === "overview" && (
            <OverviewView
              snapshot={snapshot}
              selectedRunId={selectedRunId}
              onSelectRun={selectRun}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
            />
          )}
          {activeView === "runs" && (
            <RunDetailView
              snapshot={snapshot}
              selectedRunId={selectedRunId}
              onSelectRun={selectRun}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
            />
          )}
          {activeView === "comparison" && (
            <ComparisonView
              snapshot={snapshot}
              filter={failureFilter}
              onFilterChange={setFailureFilter}
              onSelectTrace={selectTrace}
            />
          )}
          {activeView === "traces" && (
            <TracesView
              traceCases={snapshot.traceCases}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
            />
          )}
          {activeView === "calibration" && (
            <CalibrationPanel signals={calibrationSignals} points={scatterPoints} />
          )}
          {activeView === "settings" && <SettingsView rules={snapshot.gateRules} />}
        </main>
      </div>
    </div>
  );
}
