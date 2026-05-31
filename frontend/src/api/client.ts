import { benchmarkSummary, metrics, runs, traceCases } from "../data/demo";

export interface DashboardSnapshot {
  benchmarkSummary: typeof benchmarkSummary;
  metrics: typeof metrics;
  runs: typeof runs;
  traceCases: typeof traceCases;
}

export async function loadDashboardSnapshot(
  apiBaseUrl = import.meta.env.VITE_API_BASE_URL,
): Promise<DashboardSnapshot> {
  if (!apiBaseUrl) {
    return { benchmarkSummary, metrics, runs, traceCases };
  }

  const response = await fetch(`${apiBaseUrl}/api/dashboard/demo`);
  if (!response.ok) {
    throw new Error(`Dashboard API returned ${response.status}`);
  }
  return response.json() as Promise<DashboardSnapshot>;
}
