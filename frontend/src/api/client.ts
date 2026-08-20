import {
  type BenchmarkSummary,
  type GateRule,
  type MetricSummary,
  type RunRow,
  type TagBreakdownRow,
  type TraceCase,
  type TracePagination,
  benchmarkSummary,
  gateRules,
  metrics,
  runs,
  tagBreakdown,
  traceCases,
  tracePagination,
} from "../data/demo";

export interface DashboardSnapshot {
  dataSource: "live" | "demo";
  comparisonId: string | null;
  benchmarkSummary: BenchmarkSummary;
  metrics: MetricSummary[];
  runs: RunRow[];
  traceCases: TraceCase[];
  tracePagination: TracePagination;
  tagBreakdown: TagBreakdownRow[];
  gateRules: GateRule[];
}

interface RunRecord {
  id: string;
  status: "completed" | "partial" | "running" | "failed" | "cancelled" | "timed_out";
}

interface RunDemoOptions {
  apiBaseUrl?: string;
  runLabel?: string;
  pollIntervalMs?: number;
  pollTimeoutMs?: number;
  onStatus?: (message: string) => void;
}

interface LoginOptions {
  email: string;
  password: string;
  organizationSlug?: string;
  apiBaseUrl?: string;
}

interface LoginResponse {
  access_token: string;
  role: "owner" | "admin" | "evaluator" | "viewer";
  organization: { id: string; name: string; slug: string };
  user: { id: string; email: string; display_name: string };
}

const API_KEY_SESSION_KEY = "evalforge.api-key";

export function setSessionApiKey(apiKey: string): void {
  const normalized = apiKey.trim();
  if (normalized) {
    window.sessionStorage.setItem(API_KEY_SESSION_KEY, normalized);
  } else {
    window.sessionStorage.removeItem(API_KEY_SESSION_KEY);
  }
}

export async function login({
  email,
  password,
  organizationSlug,
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
}: LoginOptions): Promise<LoginResponse> {
  const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      organization_slug: organizationSlug?.trim() || null,
    }),
  });
  if (!response.ok) {
    throw new Error(
      response.status === 401 ? "Invalid sign-in details" : `Sign-in failed (${response.status})`,
    );
  }
  if (!response.headers.get("Content-Type")?.includes("application/json")) {
    throw new Error("Sign-in API did not return JSON");
  }
  const payload = (await response.json()) as LoginResponse;
  setSessionApiKey(payload.access_token);
  return payload;
}

const demoCorpus = [
  {
    doc_id: "python-venv",
    text: "The venv module creates lightweight Python virtual environments.",
    answer: "Python uses the venv module for virtual environments.",
  },
  {
    doc_id: "python-json",
    text: "The json module encodes and decodes JSON documents.",
    answer: "Python uses the json module for JSON documents.",
  },
];

const demoCases = [
  {
    external_id: "ui-case-001",
    payload: {
      input: { question: "Which Python module creates virtual environments?" },
      expected_output: "Python uses venv for virtual environments.",
      expected_facts: ["venv", "virtual environments"],
      expected_doc_id: "python-venv",
      forbidden_claims: ["quantum database"],
      tags: ["retrieval_required"],
    },
  },
  {
    external_id: "ui-case-002",
    payload: {
      input: { question: "Which Python module handles JSON documents?" },
      expected_output: "Python uses json for JSON documents.",
      expected_facts: ["json", "JSON documents"],
      expected_doc_id: "python-json",
      forbidden_claims: ["quantum database"],
      tags: ["retrieval_required"],
    },
  },
];

export async function loadDashboardSnapshot(
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
  allowDemo = import.meta.env.VITE_DEMO_MODE === "true",
): Promise<DashboardSnapshot> {
  let latestError: unknown;
  try {
    return await fetchDashboardSnapshot(`${apiBaseUrl}/api/dashboard/latest`);
  } catch (error) {
    latestError = error;
  }

  if (allowDemo) {
    try {
      return await fetchDashboardSnapshot(`${apiBaseUrl}/api/dashboard/demo`);
    } catch {
      return localDemoSnapshot();
    }
  }

  throw new Error(
    `Unable to load a persisted comparison: ${errorMessage(latestError)}. ` +
      "Run an evaluation or enable VITE_DEMO_MODE=true for explicit demo data.",
  );
}

function localDemoSnapshot(): DashboardSnapshot {
  return {
    dataSource: "demo",
    comparisonId: null,
    benchmarkSummary,
    metrics,
    runs,
    traceCases,
    tracePagination,
    tagBreakdown,
    gateRules,
  };
}

export async function runDemoEvaluation({
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
  runLabel = String(Date.now()),
  pollIntervalMs = 1000,
  pollTimeoutMs = 120000,
  onStatus,
}: RunDemoOptions = {}): Promise<DashboardSnapshot> {
  onStatus?.("Creating evaluation project");
  const app = await postJson<{ id: string }>(`${apiBaseUrl}/api/apps`, {
    name: `demo-rag-ui-${runLabel}`,
    description: "Dashboard-launched RAG evaluation",
  });
  const baselineVersion = await postJson<{ id: string }>(
    `${apiBaseUrl}/api/apps/${app.id}/versions`,
    {
      name: `baseline-${runLabel}`,
      adapter_module: "app.adapters.demo_rag",
      config: { top_k: 1, corpus: demoCorpus, latency_ms: 120 },
    },
  );
  const candidateVersion = await postJson<{ id: string }>(
    `${apiBaseUrl}/api/apps/${app.id}/versions`,
    {
      name: `candidate-${runLabel}`,
      adapter_module: "app.adapters.demo_rag",
      config: {
        top_k: 1,
        corpus: demoCorpus,
        latency_ms: 260,
        failure_mode: "hallucinate",
      },
    },
  );
  const suite = await postJson<{ id: string }>(`${apiBaseUrl}/api/apps/${app.id}/suites`, {
    name: `ui-smoke-${runLabel}`,
  });
  await postJson(`${apiBaseUrl}/api/suites/${suite.id}/cases/import`, { cases: demoCases });
  const evaluatorConfig = await postJson<{ id: string }>(`${apiBaseUrl}/api/evaluator-configs`, {
    name: `ui-rag-evaluators-${runLabel}`,
    config: {
      evaluators: [
        { name: "contains_keywords", threshold: 0.8 },
        { name: "token_f1_overlap", threshold: 0.5 },
        { name: "retrieval_hit_rate" },
        { name: "forbidden_claim" },
        { name: "latency_threshold", threshold_ms: 200 },
        { name: "cost_threshold", threshold_usd: 0.01 },
      ],
    },
  });

  onStatus?.("Running baseline");
  const baselineRun = await waitForTerminalRun(
    await createRun(apiBaseUrl, baselineVersion.id, suite.id, evaluatorConfig.id),
    apiBaseUrl,
    pollIntervalMs,
    pollTimeoutMs,
  );
  assertComparableRun(baselineRun);
  onStatus?.("Running candidate");
  const candidateRun = await waitForTerminalRun(
    await createRun(apiBaseUrl, candidateVersion.id, suite.id, evaluatorConfig.id),
    apiBaseUrl,
    pollIntervalMs,
    pollTimeoutMs,
  );
  assertComparableRun(candidateRun);

  onStatus?.("Computing comparison");
  await postJson(`${apiBaseUrl}/api/comparisons`, {
    baseline_run_id: baselineRun.id,
    candidate_run_id: candidateRun.id,
  });
  onStatus?.("Refreshing dashboard");
  return loadDashboardSnapshot(apiBaseUrl, false);
}

async function fetchDashboardSnapshot(url: string): Promise<DashboardSnapshot> {
  const authHeaders = sessionAuthHeaders();
  const response = Object.keys(authHeaders).length
    ? await fetch(url, { headers: authHeaders })
    : await fetch(url);
  if (!response.ok) {
    throw new Error(`Dashboard API returned ${response.status}`);
  }
  if (!response.headers.get("Content-Type")?.includes("application/json")) {
    throw new Error("Dashboard API did not return JSON");
  }
  return response.json() as Promise<DashboardSnapshot>;
}

async function createRun(
  apiBaseUrl: string,
  appVersionId: string,
  suiteId: string,
  evaluatorConfigId: string,
): Promise<RunRecord> {
  return postJson<RunRecord>(`${apiBaseUrl}/api/runs`, {
    app_version_id: appVersionId,
    suite_id: suiteId,
    evaluator_config_id: evaluatorConfigId,
  });
}

async function waitForTerminalRun(
  run: RunRecord,
  apiBaseUrl: string,
  pollIntervalMs: number,
  pollTimeoutMs: number,
): Promise<RunRecord> {
  if (isTerminalRun(run)) {
    return run;
  }

  const deadline = Date.now() + pollTimeoutMs;
  let currentRun = run;
  while (!isTerminalRun(currentRun)) {
    if (Date.now() > deadline) {
      throw new Error(`Run ${run.id} did not finish before timeout`);
    }
    await sleep(pollIntervalMs);
    currentRun = await fetchJson<RunRecord>(`${apiBaseUrl}/api/runs/${run.id}`);
  }
  return currentRun;
}

function isTerminalRun(run: RunRecord): boolean {
  return ["completed", "partial", "failed", "cancelled", "timed_out"].includes(run.status);
}

function assertComparableRun(run: RunRecord): void {
  if (run.status !== "completed" && run.status !== "partial") {
    throw new Error(`Run ${run.id} ended with status ${run.status} before comparison`);
  }
}

async function postJson<T = unknown>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  for (const [name, value] of Object.entries(sessionAuthHeaders())) {
    headers.set(name, value);
  }
  const response = await fetch(url, { ...init, headers });
  if (!response.ok) {
    throw new Error(`API returned ${response.status} for ${url}`);
  }
  if (!response.headers.get("Content-Type")?.includes("application/json")) {
    throw new Error(`API did not return JSON for ${url}`);
  }
  return response.json() as Promise<T>;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "unknown dashboard error";
}

function sessionAuthHeaders(): Record<string, string> {
  const apiKey = window.sessionStorage.getItem(API_KEY_SESSION_KEY);
  return apiKey ? { "X-EvalForge-Api-Key": apiKey } : {};
}
