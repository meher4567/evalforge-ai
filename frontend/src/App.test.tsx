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
});
