import { expect, test } from "@playwright/test";

test("launches an evaluation and refreshes the dashboard", async ({ page }) => {
  let latestRequests = 0;
  let versionRequests = 0;
  let runRequests = 0;
  let comparisonCreated = false;

  await page.route("**/api/dashboard/latest", async (route) => {
    latestRequests += 1;
    await route.fulfill({ json: dashboardSnapshot(comparisonCreated ? 3 : 2) });
  });
  await page.route("**/api/apps", async (route) => {
    await page.waitForTimeout(100);
    await route.fulfill({ json: { id: "app-1" }, status: 201 });
  });
  await page.route("**/api/apps/app-1/versions", async (route) => {
    versionRequests += 1;
    await route.fulfill({
      json: { id: versionRequests === 1 ? "baseline-version" : "candidate-version" },
      status: 201,
    });
  });
  await page.route("**/api/apps/app-1/suites", async (route) => {
    await route.fulfill({ json: { id: "suite-1" }, status: 201 });
  });
  await page.route("**/api/suites/suite-1/cases/import", async (route) => {
    await route.fulfill({ json: { imported: 2 }, status: 201 });
  });
  await page.route("**/api/evaluator-configs", async (route) => {
    await route.fulfill({ json: { id: "evaluator-config" }, status: 201 });
  });
  await page.route("**/api/runs", async (route) => {
    runRequests += 1;
    await route.fulfill({
      json: { id: runRequests === 1 ? "baseline-run" : "candidate-run", status: "completed" },
      status: 201,
    });
  });
  await page.route("**/api/comparisons", async (route) => {
    comparisonCreated = true;
    await route.fulfill({ json: { id: "comparison-1" }, status: 201 });
  });

  await page.goto("/");

  await expect(page.getByText("2 cases").first()).toBeVisible();
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page.getByRole("status")).toContainText("Creating evaluation project");
  await expect(page.getByText("3 cases").first()).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Evaluation complete");
  expect(runRequests).toBe(2);
});

function dashboardSnapshot(caseCount: number) {
  return {
    benchmarkSummary: {
      generatedAt: "2026-06-03T00:00:00Z",
      benchmark: "e2e_dashboard_flow",
      caseCount,
      totalExecutions: caseCount * 2,
      elapsedSeconds: 1.5,
      casesPerMinute: 80,
      gateVerdict: "fail",
    },
    metrics: [
      metric("pass_rate", "Pass rate", "Pass", "%", 1, 0, -1, "higher", 0.02, "fail"),
      metric(
        "semantic_similarity",
        "Semantic similarity",
        "Similarity",
        "score",
        1,
        0.28,
        -0.72,
        "higher",
        0.02,
        "fail",
      ),
      metric("p95_latency_ms", "p95 latency", "p95", "ms", 120, 260, 140, "lower", 50, "fail"),
      metric("cost_mean_usd", "Mean cost", "Cost", "usd", 0.000006, 0.000007, 0.000001, "lower", 0.001, "pass"),
    ],
    runs: [
      runRow("candidate-run", "candidate", caseCount, 0),
      runRow("baseline-run", "baseline", caseCount, 1),
    ],
    traceCases: [
      {
        id: "ui-case-001",
        tag: "retrieval_required",
        evaluator: "forbidden_claim",
        reason: "forbidden_claim failed",
        question: "Which Python module creates virtual environments?",
        expected: "Python uses venv for virtual environments.",
        baselineAnswer: "Python uses the venv module for virtual environments.",
        candidateAnswer: "Python uses a quantum database to create virtual environments.",
        semanticScore: 0.28,
        keywordScore: 0,
        retrievalHit: true,
        latencyMs: 260,
        costUsd: 0.000007,
        chunks: [
          {
            rank: 1,
            docId: "python-venv",
            text: "The venv module creates lightweight Python virtual environments.",
            score: 1,
          },
        ],
      },
    ],
    gateRules: [
      { metric: "Pass rate", direction: "higher", tolerance: "0.02", verdict: "fail" },
      { metric: "Semantic similarity", direction: "higher", tolerance: "0.02", verdict: "fail" },
      { metric: "p95 latency", direction: "lower", tolerance: "50", verdict: "fail" },
      { metric: "Mean cost", direction: "lower", tolerance: "0.001", verdict: "pass" },
    ],
  };
}

function metric(
  key: string,
  label: string,
  shortLabel: string,
  unit: string,
  baseline: number,
  candidate: number,
  delta: number,
  direction: string,
  tolerance: number,
  status: string,
) {
  return {
    key,
    label,
    shortLabel,
    unit,
    baseline,
    candidate,
    baselineCi: [baseline, baseline],
    candidateCi: [candidate, candidate],
    delta,
    deltaCi: [delta, delta],
    direction,
    tolerance,
    status,
  };
}

function runRow(id: string, version: string, cases: number, passRate: number) {
  return {
    id,
    version,
    suite: "ui-smoke",
    cases,
    passRate,
    semanticSimilarity: passRate,
    p95LatencyMs: version === "candidate" ? 260 : 120,
    costMeanUsd: 0.000007,
    createdAt: "2026-06-03T00:00:00Z",
    status: "completed",
  };
}
