import {
  Activity,
  AlertTriangle,
  BookOpen,
  FlaskConical,
  GitCompare,
  HelpCircle,
  LayoutDashboard,
  Play,
  RefreshCcw,
  Route,
  Settings,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  loadDashboardSnapshot,
  login,
  runDemoEvaluation,
  setSessionApiKey,
  type DashboardSnapshot,
} from "./api/client";
import {
  CalibrationPanel,
  CalibrationUnavailable,
  ComparisonView,
  type FailureFilter,
  OverviewView,
  PageTitle,
  RunDetailView,
  SettingsView,
  TracesView,
} from "./components/DashboardViews";
import {
  calibrationSignals,
  scatterPoints,
  type ViewId,
} from "./data/demo";

const navItems: Array<{ id: ViewId; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "runs", label: "Runs", icon: Activity },
  { id: "comparison", label: "Comparison", icon: GitCompare },
  { id: "traces", label: "Traces", icon: Route },
  { id: "calibration", label: "Calibration", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: Settings },
];

function TopBar({
  isRunningEvaluation,
  actionMessage,
  onRefresh,
  onRunEvaluation,
  snapshot,
}: {
  isRunningEvaluation: boolean;
  actionMessage: string | null;
  onRefresh: () => void;
  onRunEvaluation: () => void;
  snapshot: DashboardSnapshot | null;
}) {
  const summary = snapshot?.benchmarkSummary;
  return (
    <header className="topbar">
      <div className="topbar__selects" aria-label="Workspace filters">
        <span>Project: {summary?.projectName ?? "No comparison"}</span>
        <span>Suite: {summary?.suiteName ?? "—"}</span>
        <span className={`source-chip source-chip--${snapshot?.dataSource ?? "none"}`}>
          {snapshot?.dataSource === "live" ? "Live data" : snapshot ? "Demo data" : "No data"}
        </span>
      </div>
      <div className="topbar__actions">
        <span className="action-message" role="status" aria-live="polite" aria-atomic="true">
          {actionMessage ?? ""}
        </span>
        <button
          className="primary-action"
          type="button"
          disabled={isRunningEvaluation}
          onClick={onRunEvaluation}
        >
          <Play size={16} />
          {isRunningEvaluation ? "Running..." : "Run demo evaluation"}
        </button>
        <span className="date-chip">{formatDate(summary?.generatedAt)}</span>
        <button className="icon-button" type="button" aria-label="Refresh dashboard" onClick={onRefresh}>
          <RefreshCcw size={16} />
        </button>
      </div>
    </header>
  );
}

function Sidebar({
  activeView,
  onViewChange,
  summary,
}: {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
  summary: DashboardSnapshot["benchmarkSummary"] | null;
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
        <strong>
          {summary
            ? `${summary.candidateVersion ?? "candidate"} vs ${summary.baselineVersion ?? "baseline"}`
            : "No persisted comparison"}
        </strong>
        <button type="button" disabled={!summary} onClick={() => onViewChange("comparison")}>
          Open comparison
        </button>
      </div>
      <div className="sidebar-footer">
        <a href="https://github.com/meher4567/evalforge-ai#readme">
          <BookOpen size={17} />
          <span>Docs</span>
        </a>
        <a href="https://github.com/meher4567/evalforge-ai/issues">
          <HelpCircle size={17} />
          <span>Help</span>
        </a>
      </div>
    </aside>
  );
}

export function App() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [activeView, setActiveView] = useState<ViewId>("overview");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedTraceIndex, setSelectedTraceIndex] = useState(0);
  const [failureFilter, setFailureFilter] = useState<FailureFilter>("all");
  const [isRunningEvaluation, setIsRunningEvaluation] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    loadDashboardSnapshot()
      .then((loadedSnapshot) => {
        if (isMounted) applySnapshot(loadedSnapshot);
      })
      .catch((error) => {
        if (isMounted) setLoadError(formatError(error));
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedRun = useMemo(
    () => snapshot?.runs.find((run) => run.id === selectedRunId) ?? snapshot?.runs[0],
    [selectedRunId, snapshot],
  );

  function selectRun(runId: string) {
    setSelectedRunId(runId);
    setActiveView("runs");
  }

  function selectTrace(index: number) {
    setSelectedTraceIndex(index);
    setActiveView("traces");
  }

  function applySnapshot(loadedSnapshot: DashboardSnapshot) {
    setSnapshot(loadedSnapshot);
    setSelectedRunId(loadedSnapshot.runs[0]?.id ?? "");
    setSelectedTraceIndex(0);
    setLoadError(null);
  }

  async function refreshDashboard() {
    setIsLoading(true);
    setActionMessage("Refreshing dashboard");
    try {
      applySnapshot(await loadDashboardSnapshot());
      setActionMessage("Dashboard refreshed");
    } catch (error) {
      setLoadError(formatError(error));
      setActionMessage(`Refresh failed: ${formatError(error)}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function launchEvaluation() {
    setIsRunningEvaluation(true);
    setActionMessage(null);
    try {
      const loadedSnapshot = await runDemoEvaluation({ onStatus: setActionMessage });
      applySnapshot(loadedSnapshot);
      setActionMessage("Evaluation complete");
    } catch (error) {
      setActionMessage(`Evaluation failed: ${formatError(error)}`);
    } finally {
      setIsRunningEvaluation(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        summary={snapshot?.benchmarkSummary ?? null}
      />
      <div className="workspace">
        <TopBar
          isRunningEvaluation={isRunningEvaluation}
          actionMessage={actionMessage}
          onRefresh={refreshDashboard}
          onRunEvaluation={launchEvaluation}
          snapshot={snapshot}
        />
        <main className="workspace-main">
          {!snapshot && (
            <DashboardState isLoading={isLoading} error={loadError} onRetry={refreshDashboard} />
          )}

          {snapshot && selectedRun && (
            <>
              <PageTitle
                title={
                  activeView === "runs"
                    ? "Run detail"
                    : navItems.find((item) => item.id === activeView)?.label
                }
                selectedVersion={selectedRun.version}
                benchmark={snapshot.benchmarkSummary.benchmark}
                caseCount={snapshot.benchmarkSummary.caseCount}
                meanCost={
                  snapshot.metrics.find((metric) => metric.key === "cost_mean_usd")?.candidate ?? 0
                }
                gateVerdict={snapshot.benchmarkSummary.gateVerdict}
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
            snapshot.dataSource === "demo" ? (
              <CalibrationPanel signals={calibrationSignals} points={scatterPoints} />
            ) : (
              <CalibrationUnavailable />
            )
          )}
          {activeView === "settings" && (
            <SettingsView
              rules={snapshot.gateRules}
              verdict={snapshot.benchmarkSummary.gateVerdict}
            />
          )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function DashboardState({
  isLoading,
  error,
  onRetry,
}: {
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationSlug, setOrganizationSlug] = useState("");
  const [signInError, setSignInError] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const authenticationRequired = error?.includes("401") ?? false;

  function authenticate() {
    setSessionApiKey(apiKey);
    onRetry();
  }

  async function signIn() {
    setIsSigningIn(true);
    setSignInError(null);
    try {
      await login({ email, password, organizationSlug });
      onRetry();
    } catch (signInFailure) {
      setSignInError(formatError(signInFailure));
    } finally {
      setIsSigningIn(false);
    }
  }

  return (
    <section className="panel dashboard-state" aria-label="Dashboard status">
      <AlertTriangle size={24} />
      <h1>{isLoading ? "Loading persisted comparison" : "No comparison to display"}</h1>
      <p>{error ?? "Connecting to the EvalForge API…"}</p>
      {authenticationRequired && (
        <div className="authentication-options">
          <form
            className="authentication-form"
            onSubmit={(event) => {
              event.preventDefault();
              void signIn();
            }}
          >
            <strong>Sign in</strong>
            <label htmlFor="evalforge-email">Email</label>
            <input
              id="evalforge-email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <label htmlFor="evalforge-password">Password</label>
            <input
              id="evalforge-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <label htmlFor="evalforge-organization">Organization slug (optional)</label>
            <input
              id="evalforge-organization"
              autoComplete="organization"
              value={organizationSlug}
              onChange={(event) => setOrganizationSlug(event.target.value)}
            />
            <button
              className="primary-action"
              type="submit"
              disabled={isSigningIn || !email.trim() || !password}
            >
              {isSigningIn ? "Signing in…" : "Sign in"}
            </button>
            {signInError && <small role="alert">{signInError}</small>}
          </form>
          <span className="authentication-divider">or use an automation credential</span>
          <form
            className="authentication-form"
            onSubmit={(event) => {
              event.preventDefault();
              authenticate();
            }}
          >
            <label htmlFor="evalforge-api-key">Access token or API key</label>
            <input
              id="evalforge-api-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
            <button className="secondary-action" type="submit" disabled={!apiKey.trim()}>
              Use credential
            </button>
            <small>Credentials stay in memory and are cleared when the page refreshes.</small>
          </form>
        </div>
      )}
      {!isLoading && (
        <button className="secondary-action" type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </section>
  );
}

function formatDate(value: string | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function formatError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unexpected error";
}
