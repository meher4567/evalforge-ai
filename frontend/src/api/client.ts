import { benchmarkSummary, gateRules, metrics, runs, traceCases } from "../data/demo";

export interface DashboardSnapshot {
  benchmarkSummary: typeof benchmarkSummary;
  metrics: typeof metrics;
  runs: typeof runs;
  traceCases: typeof traceCases;
  gateRules: typeof gateRules;
}

export async function loadDashboardSnapshot(
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
): Promise<DashboardSnapshot> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/dashboard/demo`);
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }
    if (!response.headers.get("Content-Type")?.includes("application/json")) {
      throw new Error("Dashboard API did not return JSON");
    }
    return response.json() as Promise<DashboardSnapshot>;
  } catch {
    return { benchmarkSummary, metrics, runs, traceCases, gateRules };
  }
}
