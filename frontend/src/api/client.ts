import {
  benchmarkSummary,
  gateRules,
  metrics,
  runs,
  tagBreakdown,
  traceCases,
  tracePagination,
} from "../data/demo";

export interface DashboardSnapshot {
  benchmarkSummary: typeof benchmarkSummary;
  metrics: typeof metrics;
  runs: typeof runs;
  traceCases: typeof traceCases;
  tracePagination: typeof tracePagination;
  tagBreakdown: typeof tagBreakdown;
  gateRules: typeof gateRules;
}

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

  return {
    benchmarkSummary,
    metrics,
    runs,
    traceCases,
    tracePagination,
    tagBreakdown,
    gateRules,
  };
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
