import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { setSessionApiKey } from "./api/client";
import {
  benchmarkSummary,
  gateRules,
  metrics,
  runs,
  tagBreakdown,
  traceCases,
  tracePagination,
} from "./data/demo";

const demoSnapshot = {
  dataSource: "demo" as const,
  comparisonId: null,
  benchmarkSummary,
  metrics,
  runs,
  traceCases,
  tracePagination,
  tagBreakdown,
  gateRules,
};

beforeEach(() => {
  setSessionApiKey("");
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(demoSnapshot)));
});

afterEach(() => {
  setSessionApiKey("");
  vi.unstubAllGlobals();
});

describe("EvalForge dashboard", () => {
  it("renders the measured gate verdict on the overview", async () => {
    render(<App />);

    expect(screen.getByText("EvalForge AI")).toBeInTheDocument();
    expect(await screen.findByText("Regression blocked")).toBeInTheDocument();
    expect(await screen.findByText("500 cases")).toBeInTheDocument();
    expect(await screen.findByLabelText("Comparison summary")).toBeInTheDocument();
  });

  it("keeps primary navigation buttons accessible when labels collapse", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "Comparison" })).toHaveAttribute(
      "aria-label",
      "Comparison",
    );
  });

  it("filters failures from the comparison screen", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Comparison" }));
    fireEvent.click(await screen.findByRole("button", { name: "forbidden claim" }));

    expect(screen.getByText("demo-0010")).toBeInTheDocument();
    expect(screen.queryByText("demo-0001")).not.toBeInTheDocument();
  });

  it("shows per-tag quality breakdown on the comparison screen", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Comparison" }));

    expect(await screen.findByRole("heading", { name: "Tag breakdown" })).toBeInTheDocument();
    expect(screen.getByText("Candidate pass rate by first case tag")).toBeInTheDocument();
  });

  it("moves through failed traces", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Traces" }));
    expect(await screen.findByText("demo-0001 | hallucination_risk")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next failed case" }));
    expect(screen.getByText("demo-0007 | reasoning_required")).toBeInTheDocument();
  });

  it("marks calibration as a preview, not a finished gold-set result", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Calibration" }));

    expect(await screen.findByText("Calibration preview")).toBeInTheDocument();
    expect(screen.getByText("methodology pending")).toBeInTheDocument();
  });

  it("hydrates dashboard data from the backend snapshot when available", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          dataSource: "live",
          comparisonId: "comparison-321",
          benchmarkSummary: {
            ...benchmarkSummary,
            caseCount: 321,
            totalExecutions: 642,
          },
          metrics,
          runs,
          traceCases,
          tracePagination,
          tagBreakdown,
          gateRules,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("321 cases")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/dashboard/latest");
  });

  it("launches a fresh evaluation from the dashboard action bar", async () => {
    const initialSnapshot = {
      ...demoSnapshot,
      dataSource: "live" as const,
      comparisonId: "comparison-initial",
      benchmarkSummary: {
        ...benchmarkSummary,
        caseCount: 2,
        totalExecutions: 4,
      },
    };
    const refreshedSnapshot = {
      ...initialSnapshot,
      benchmarkSummary: {
        ...initialSnapshot.benchmarkSummary,
        caseCount: 3,
        totalExecutions: 6,
      },
    };
    let latestRequests = 0;
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/dashboard/latest") {
        latestRequests += 1;
        return new Response(JSON.stringify(latestRequests === 1 ? initialSnapshot : refreshedSnapshot), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url === "/api/apps") return jsonResponse({ id: "app-1" });
      if (url === "/api/apps/app-1/versions") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return jsonResponse({ id: callCount === 1 ? "baseline-version" : "candidate-version" });
      }
      if (url === "/api/apps/app-1/suites") return jsonResponse({ id: "suite-1" });
      if (url === "/api/suites/suite-1/cases/import") return jsonResponse({ imported: 2 });
      if (url === "/api/evaluator-configs") return jsonResponse({ id: "evaluator-config" });
      if (url === "/api/runs") {
        const callCount = fetchMock.mock.calls.filter((call) => call[0] === url).length;
        return jsonResponse({
          id: callCount === 1 ? "baseline-run" : "candidate-run",
          status: "completed",
        });
      }
      if (url === "/api/comparisons") return jsonResponse({ id: "comparison-1" });
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("2 cases")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run demo evaluation" }));

    expect(screen.getByRole("status")).toHaveTextContent("Creating evaluation project");
    expect(await screen.findByText("3 cases")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Evaluation complete");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/apps",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("announces evaluation failures with the returned error message", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/dashboard/latest") {
        return jsonResponse({
          ...demoSnapshot,
          dataSource: "live",
          comparisonId: "comparison-500",
          benchmarkSummary,
        });
      }
      if (url === "/api/apps") {
        return new Response(JSON.stringify({ detail: "App name already exists" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findByText("500 cases");
    fireEvent.click(screen.getByRole("button", { name: "Run demo evaluation" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Evaluation failed: API returned 409 for /api/apps",
    );
  });

  it("shows an honest empty state instead of silent demo data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("missing", { status: 404 })),
    );

    render(<App />);

    expect(await screen.findByText("No comparison to display")).toBeInTheDocument();
    expect(screen.queryByText("Regression blocked")).not.toBeInTheDocument();
    expect(screen.getByText(/enable VITE_DEMO_MODE=true/)).toBeInTheDocument();
  });

  it("authenticates with a tab-scoped API key", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Valid EvalForge API key required" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ...demoSnapshot, dataSource: "live" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const input = await screen.findByLabelText("Access token or API key");
    fireEvent.change(input, { target: { value: "session-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Use credential" }));

    expect(await screen.findByText("Regression blocked")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/dashboard/latest",
      expect.objectContaining({ headers: { "X-EvalForge-Api-Key": "session-secret" } }),
    );
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
