import { afterEach, describe, expect, it, vi } from "vitest";
import { loadDashboardSnapshot, type DashboardSnapshot } from "./client";
import {
  benchmarkSummary,
  gateRules,
  metrics,
  runs,
  tagBreakdown,
  traceCases,
  tracePagination,
} from "../data/demo";

function snapshotWithCaseCount(caseCount: number): DashboardSnapshot {
  return {
    benchmarkSummary: {
      ...benchmarkSummary,
      caseCount,
      totalExecutions: caseCount * 2,
    },
    metrics,
    runs,
    traceCases,
    tracePagination,
    tagBreakdown,
    gateRules,
  };
}

function jsonResponse(body: DashboardSnapshot): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadDashboardSnapshot", () => {
  it("loads the latest persisted dashboard snapshot first", async () => {
    const latestSnapshot = snapshotWithCaseCount(321);
    const fetchMock = vi.fn(async () => jsonResponse(latestSnapshot));
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await loadDashboardSnapshot();

    expect(snapshot.benchmarkSummary.caseCount).toBe(321);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/dashboard/latest");
  });

  it("falls back to the demo endpoint when latest comparison is unavailable", async () => {
    const demoSnapshot = snapshotWithCaseCount(500);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("missing", { status: 404 }))
      .mockResolvedValueOnce(jsonResponse(demoSnapshot));
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await loadDashboardSnapshot();

    expect(snapshot.benchmarkSummary.caseCount).toBe(500);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/dashboard/latest");
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/dashboard/demo");
  });

  it("uses local demo data when API responses are not JSON", async () => {
    const htmlResponse = new Response("<html></html>", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
    const fetchMock = vi.fn(async () => htmlResponse);
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await loadDashboardSnapshot();

    expect(snapshot.benchmarkSummary.caseCount).toBe(benchmarkSummary.caseCount);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
