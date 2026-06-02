import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { benchmarkSummary, gateRules, metrics, runs, traceCases } from "./data/demo";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("EvalForge dashboard", () => {
  it("renders the measured gate verdict on the overview", () => {
    render(<App />);

    expect(screen.getByText("EvalForge AI")).toBeInTheDocument();
    expect(screen.getByText("Regression blocked")).toBeInTheDocument();
    expect(screen.getByText("500 cases")).toBeInTheDocument();
    expect(screen.getByLabelText("Comparison summary")).toBeInTheDocument();
  });

  it("filters failures from the comparison screen", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Comparison" }));
    fireEvent.click(screen.getByRole("button", { name: "forbidden claim" }));

    expect(screen.getByText("demo-0010")).toBeInTheDocument();
    expect(screen.queryByText("demo-0001")).not.toBeInTheDocument();
  });

  it("moves through failed traces", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Traces" }));
    expect(screen.getByText("demo-0001 | hallucination_risk")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next failed case" }));
    expect(screen.getByText("demo-0007 | reasoning_required")).toBeInTheDocument();
  });

  it("marks calibration as a preview, not a finished gold-set result", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Calibration" }));

    expect(screen.getByText("Calibration preview")).toBeInTheDocument();
    expect(screen.getByText("methodology pending")).toBeInTheDocument();
  });

  it("hydrates dashboard data from the backend snapshot when available", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          benchmarkSummary: {
            ...benchmarkSummary,
            caseCount: 321,
            totalExecutions: 642,
          },
          metrics,
          runs,
          traceCases,
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
      benchmarkSummary: {
        ...benchmarkSummary,
        caseCount: 2,
        totalExecutions: 4,
      },
      metrics,
      runs,
      traceCases,
      gateRules,
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
    fireEvent.click(screen.getByRole("button", { name: "Run evaluation" }));

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
          benchmarkSummary,
          metrics,
          runs,
          traceCases,
          gateRules,
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
    fireEvent.click(screen.getByRole("button", { name: "Run evaluation" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Evaluation failed: API returned 409 for /api/apps",
    );
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
