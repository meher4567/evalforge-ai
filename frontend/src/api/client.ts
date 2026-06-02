import { benchmarkSummary, gateRules, metrics, runs, traceCases } from "../data/demo";

export interface DashboardSnapshot {
  benchmarkSummary: typeof benchmarkSummary;
  metrics: typeof metrics;
  runs: typeof runs;
  traceCases: typeof traceCases;
  gateRules: typeof gateRules;
}

interface RunRecord {
  id: string;
  status: "completed" | "partial" | "running" | "failed";
}

interface RunDemoOptions {
  apiBaseUrl?: string;
  runLabel?: string;
  pollIntervalMs?: number;
  pollTimeoutMs?: number;
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
): Promise<DashboardSnapshot> {
  const latest = await fetchDashboardSnapshot(`${apiBaseUrl}/api/dashboard/latest`);
  if (latest) {
    return latest;
  }

  const demo = await fetchDashboardSnapshot(`${apiBaseUrl}/api/dashboard/demo`);
  if (demo) {
    return demo;
  }

  return { benchmarkSummary, metrics, runs, traceCases, gateRules };
}

export async function runDemoEvaluation({
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
  runLabel = String(Date.now()),
  pollIntervalMs = 1000,
  pollTimeoutMs = 120000,
}: RunDemoOptions = {}): Promise<DashboardSnapshot> {
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
        { name: "semantic_similarity", threshold: 0.5 },
        { name: "retrieval_hit_rate" },
        { name: "forbidden_claim" },
        { name: "latency_threshold", threshold_ms: 200 },
        { name: "cost_threshold", threshold_usd: 0.01 },
      ],
    },
  });

  const baselineRun = await waitForTerminalRun(
    await createRun(apiBaseUrl, baselineVersion.id, suite.id, evaluatorConfig.id),
    apiBaseUrl,
    pollIntervalMs,
    pollTimeoutMs,
  );
  const candidateRun = await waitForTerminalRun(
    await createRun(apiBaseUrl, candidateVersion.id, suite.id, evaluatorConfig.id),
    apiBaseUrl,
    pollIntervalMs,
    pollTimeoutMs,
  );

  await postJson(`${apiBaseUrl}/api/comparisons`, {
    baseline_run_id: baselineRun.id,
    candidate_run_id: candidateRun.id,
  });
  return loadDashboardSnapshot(apiBaseUrl);
}

async function fetchDashboardSnapshot(url: string): Promise<DashboardSnapshot | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }
    if (!response.headers.get("Content-Type")?.includes("application/json")) {
      throw new Error("Dashboard API did not return JSON");
    }
    return response.json() as Promise<DashboardSnapshot>;
  } catch {
    return null;
  }
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
  return run.status === "completed" || run.status === "partial";
}

async function postJson<T = unknown>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
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
