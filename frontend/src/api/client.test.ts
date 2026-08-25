import { afterEach, describe, expect, it, vi } from "vitest";
import {
  login,
  loadDashboardSnapshot,
  runDemoEvaluation,
  setSessionApiKey,
  type DashboardSnapshot,
} from "./client";
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
    dataSource: "live",
    comparisonId: `comparison-${caseCount}`,
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

function apiResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  setSessionApiKey("");
  vi.unstubAllGlobals();
});

describe("loadDashboardSnapshot", () => {
  it("loads the latest persisted dashboard snapshot first", async () => {
    const latestSnapshot = snapshotWithCaseCount(321);
    const fetchMock = vi.fn(async () => jsonResponse(latestSnapshot));
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await loadDashboardSnapshot("", true);

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

    const snapshot = await loadDashboardSnapshot("", true);

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

    const snapshot = await loadDashboardSnapshot("", true);

    expect(snapshot.benchmarkSummary.caseCount).toBe(benchmarkSummary.caseCount);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not silently substitute demo data in normal mode", async () => {
    const fetchMock = vi.fn(async () => new Response("missing", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboardSnapshot("", false)).rejects.toThrow(
      "Unable to load a persisted comparison",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/dashboard/latest");
  });
});

describe("login", () => {
  it("keeps the organization-scoped session token in memory only", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/auth/login") {
        return apiResponse({
          access_token: "efs_session-token",
          role: "evaluator",
          organization: { id: "org-1", name: "Alpha", slug: "alpha" },
          user: { id: "user-1", email: "user@example.com", display_name: "User" },
        });
      }
      if (url === "/api/dashboard/latest") {
        return jsonResponse(snapshotWithCaseCount(1));
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const principal = await login({
      email: "user@example.com",
      password: "password-long-enough",
      organizationSlug: "alpha",
    });

    expect(principal.role).toBe("evaluator");
    expect(window.sessionStorage.length).toBe(0);
    await loadDashboardSnapshot("", false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "user@example.com",
          password: "password-long-enough",
          organization_slug: "alpha",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith("/api/dashboard/latest", {
      headers: { "X-EvalForge-Api-Key": "efs_session-token" },
    });
  });
});

describe("runDemoEvaluation", () => {
  it("creates a fresh evaluation through the public API and reloads the dashboard", async () => {
    const latestSnapshot = snapshotWithCaseCount(2);
    const statusUpdates: string[] = [];
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/apps") return apiResponse({ id: "app-1" }, 201);
      if (url === "/api/apps/app-1/versions") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return apiResponse({ id: callCount === 1 ? "baseline-version" : "candidate-version" }, 201);
      }
      if (url === "/api/apps/app-1/suites") return apiResponse({ id: "suite-1" }, 201);
      if (url === "/api/suites/suite-1/cases/import") return apiResponse({ imported: 2 }, 201);
      if (url === "/api/evaluator-configs") return apiResponse({ id: "evaluator-config" }, 201);
      if (url === "/api/runs") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return apiResponse(
          { id: callCount === 1 ? "baseline-run" : "candidate-run", status: "completed" },
          201,
        );
      }
      if (url === "/api/comparisons") return apiResponse({ id: "comparison-1" }, 201);
      if (url === "/api/dashboard/latest") return jsonResponse(latestSnapshot);
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await runDemoEvaluation({
      runLabel: "test-run",
      onStatus: (message) => statusUpdates.push(message),
    });

    expect(snapshot.benchmarkSummary.caseCount).toBe(2);
    expect(statusUpdates).toEqual([
      "Creating evaluation project",
      "Running baseline",
      "Running candidate",
      "Computing comparison",
      "Refreshing dashboard",
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/apps",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/comparisons",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          baseline_run_id: "baseline-run",
          candidate_run_id: "candidate-run",
        }),
      }),
    );
  });

  it("polls running runs before creating the comparison", async () => {
    const latestSnapshot = snapshotWithCaseCount(2);
    const runPolls = new Map([
      ["baseline-run", ["running", "completed"]],
      ["candidate-run", ["running", "completed"]],
    ]);
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/apps") return apiResponse({ id: "app-1" }, 201);
      if (url === "/api/apps/app-1/versions") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return apiResponse({ id: callCount === 1 ? "baseline-version" : "candidate-version" }, 201);
      }
      if (url === "/api/apps/app-1/suites") return apiResponse({ id: "suite-1" }, 201);
      if (url === "/api/suites/suite-1/cases/import") return apiResponse({ imported: 2 }, 201);
      if (url === "/api/evaluator-configs") return apiResponse({ id: "evaluator-config" }, 201);
      if (url === "/api/runs") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return apiResponse(
          { id: callCount === 1 ? "baseline-run" : "candidate-run", status: "running" },
          201,
        );
      }
      if (url.startsWith("/api/runs/")) {
        const runId = url.replace("/api/runs/", "");
        const statuses = runPolls.get(runId) ?? ["completed"];
        const status = statuses.shift() ?? "completed";
        return apiResponse({ id: runId, status });
      }
      if (url === "/api/comparisons") return apiResponse({ id: "comparison-1" }, 201);
      if (url === "/api/dashboard/latest") return jsonResponse(latestSnapshot);
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await runDemoEvaluation({ pollIntervalMs: 0, runLabel: "celery-run" });

    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/runs/baseline-run")).toBe(true);
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/runs/candidate-run")).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/comparisons",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("stops immediately when a run reaches a non-comparable terminal state", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/apps") return apiResponse({ id: "app-1" }, 201);
      if (url === "/api/apps/app-1/versions") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return apiResponse({ id: callCount === 1 ? "baseline-version" : "candidate-version" }, 201);
      }
      if (url === "/api/apps/app-1/suites") return apiResponse({ id: "suite-1" }, 201);
      if (url === "/api/suites/suite-1/cases/import") return apiResponse({ imported: 2 }, 201);
      if (url === "/api/evaluator-configs") return apiResponse({ id: "evaluator-config" }, 201);
      if (url === "/api/runs") {
        return apiResponse({ id: "baseline-run", status: "timed_out" }, 201);
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(runDemoEvaluation({ runLabel: "timed-out" })).rejects.toThrow(
      "ended with status timed_out",
    );
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/comparisons")).toBe(false);
  });
});
