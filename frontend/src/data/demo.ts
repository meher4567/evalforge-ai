export type ViewId =
  | "overview"
  | "runs"
  | "comparison"
  | "traces"
  | "calibration"
  | "settings";

export type MetricKey =
  | "pass_rate"
  | "semantic_similarity"
  | "p95_latency_ms"
  | "cost_mean_usd";

export type MetricDirection = "higher" | "lower";

export interface MetricSummary {
  key: MetricKey;
  label: string;
  shortLabel: string;
  unit: string;
  baseline: number;
  candidate: number;
  baselineCi: [number, number];
  candidateCi: [number, number];
  delta: number;
  deltaCi: [number, number];
  direction: MetricDirection;
  tolerance: number;
  status: "pass" | "warn" | "fail";
}

export interface RunRow {
  id: string;
  version: string;
  suite: string;
  cases: number;
  passRate: number;
  semanticSimilarity: number;
  p95LatencyMs: number;
  costMeanUsd: number;
  createdAt: string;
  status: "completed" | "partial" | "running";
}

export interface RetrievedChunk {
  rank: number;
  docId: string;
  text: string;
  score: number;
}

export interface TraceCase {
  id: string;
  tag: string;
  evaluator: string;
  reason: string;
  question: string;
  expected: string;
  baselineAnswer: string;
  candidateAnswer: string;
  semanticScore: number;
  keywordScore: number;
  retrievalHit: boolean;
  latencyMs: number;
  costUsd: number;
  chunks: RetrievedChunk[];
}

export interface TracePagination {
  total: number;
  limit: number;
  offset: number;
  returned: number;
}

export interface TagBreakdownRow {
  tag: string;
  baselineCaseCount: number;
  candidateCaseCount: number;
  candidateFailureCount: number;
  candidatePassRate: number;
}

export interface CalibrationSignal {
  evaluator: string;
  pearson: number;
  spearman: number;
  agreementRate: number;
  finding: string;
}

export interface ScatterPoint {
  id: string;
  evaluatorScore: number;
  humanLabel: number;
  tag: string;
}

export interface GateRule {
  metric: string;
  direction: MetricDirection;
  tolerance: string;
  verdict: "pass" | "warn" | "fail";
}

export const benchmarkSummary = {
  generatedAt: "2026-05-31T12:30:56Z",
  benchmark: "deterministic_demo_rag_regression",
  reproductionCommand:
    "uv run --directory backend python ../benchmarks/run_demo.py --cases 500",
  caseCount: 500,
  totalExecutions: 1000,
  elapsedSeconds: 12.162,
  casesPerMinute: 4933.21,
  gateVerdict: "fail" as const,
};

export const metrics: MetricSummary[] = [
  {
    key: "pass_rate",
    label: "Pass rate",
    shortLabel: "Pass",
    unit: "%",
    baseline: 1,
    candidate: 0,
    baselineCi: [1, 1],
    candidateCi: [0, 0],
    delta: -1,
    deltaCi: [-1, -1],
    direction: "higher",
    tolerance: 0.02,
    status: "fail",
  },
  {
    key: "semantic_similarity",
    label: "Token overlap",
    shortLabel: "Overlap",
    unit: "score",
    baseline: 1,
    candidate: 0.284951,
    baselineCi: [1, 1],
    candidateCi: [0.278851, 0.290957],
    delta: -0.715049,
    deltaCi: [-0.721149, -0.709043],
    direction: "higher",
    tolerance: 0.02,
    status: "fail",
  },
  {
    key: "p95_latency_ms",
    label: "p95 latency",
    shortLabel: "p95",
    unit: "ms",
    baseline: 120,
    candidate: 260,
    baselineCi: [120, 120],
    candidateCi: [260, 260],
    delta: 140,
    deltaCi: [140, 140],
    direction: "lower",
    tolerance: 50,
    status: "fail",
  },
  {
    key: "cost_mean_usd",
    label: "Mean cost",
    shortLabel: "Cost",
    unit: "usd",
    baseline: 0.000004,
    candidate: 0.000004,
    baselineCi: [0.000004, 0.000004],
    candidateCi: [0.000004, 0.000004],
    delta: 0,
    deltaCi: [0, 0],
    direction: "lower",
    tolerance: 0.2,
    status: "pass",
  },
];

export const runs: RunRow[] = [
  {
    id: "run_candidate_500",
    version: "v2_candidate_hallucination_injected",
    suite: "demo_rag_500",
    cases: 500,
    passRate: 0,
    semanticSimilarity: 0.284951,
    p95LatencyMs: 260,
    costMeanUsd: 0.000004,
    createdAt: "2026-05-31 18:00 IST",
    status: "completed",
  },
  {
    id: "run_baseline_500",
    version: "v1_baseline_bge_top3",
    suite: "demo_rag_500",
    cases: 500,
    passRate: 1,
    semanticSimilarity: 1,
    p95LatencyMs: 120,
    costMeanUsd: 0.000004,
    createdAt: "2026-05-31 17:59 IST",
    status: "completed",
  },
  {
    id: "run_prompt_rewrite_100",
    version: "v3_prompt_rewrite_preview",
    suite: "demo_rag_100",
    cases: 100,
    passRate: 0.94,
    semanticSimilarity: 0.91,
    p95LatencyMs: 188,
    costMeanUsd: 0.000005,
    createdAt: "2026-05-30 22:18 IST",
    status: "completed",
  },
  {
    id: "run_flaky_subset",
    version: "v1_baseline_rerun_n5",
    suite: "flaky_subset_50",
    cases: 250,
    passRate: 0.972,
    semanticSimilarity: 0.956,
    p95LatencyMs: 142,
    costMeanUsd: 0.000004,
    createdAt: "2026-05-30 20:41 IST",
    status: "partial",
  },
];

export const traceCases: TraceCase[] = [
  {
    id: "demo-0001",
    tag: "hallucination_risk",
    evaluator: "token_f1_overlap",
    reason: "Candidate answered with forbidden synthetic claim",
    question: "Which Python module is used for venv?",
    expected: "Python uses the venv module for virtual environments.",
    baselineAnswer: "Python uses the venv module for virtual environments.",
    candidateAnswer:
      "Python uses a telepathic compiler backed by a quantum database for venv.",
    semanticScore: 0.25,
    keywordScore: 0,
    retrievalHit: true,
    latencyMs: 260,
    costUsd: 0.000004,
    chunks: [
      {
        rank: 1,
        docId: "python-venv",
        text: "The venv module creates lightweight Python virtual environments.",
        score: 0.96,
      },
      {
        rank: 2,
        docId: "python-pathlib",
        text: "The pathlib module represents filesystem paths as objects.",
        score: 0.44,
      },
      {
        rank: 3,
        docId: "python-unittest",
        text: "The unittest module supports test automation and shared setup code.",
        score: 0.39,
      },
    ],
  },
  {
    id: "demo-0007",
    tag: "reasoning_required",
    evaluator: "contains_keywords",
    reason: "Expected facts were missing from the generated answer",
    question: "Which Python module is used for asyncio?",
    expected: "Python uses asyncio for async concurrency.",
    baselineAnswer: "Python uses asyncio for async concurrency.",
    candidateAnswer:
      "Python uses a quantum database for async code and does not need modules.",
    semanticScore: 0.31,
    keywordScore: 0,
    retrievalHit: true,
    latencyMs: 260,
    costUsd: 0.000004,
    chunks: [
      {
        rank: 1,
        docId: "python-asyncio",
        text: "The asyncio module supports concurrent code with async and await syntax.",
        score: 0.94,
      },
      {
        rank: 2,
        docId: "python-logging",
        text: "The logging module provides flexible event logging for applications.",
        score: 0.35,
      },
      {
        rank: 3,
        docId: "python-json",
        text: "The json module encodes and decodes JSON documents.",
        score: 0.32,
      },
    ],
  },
  {
    id: "demo-0010",
    tag: "edge_case",
    evaluator: "forbidden_claim",
    reason: "Forbidden claim matched the generated answer",
    question: "Which Python module is used for sqlite3?",
    expected: "Python uses sqlite3 for SQLite database access.",
    baselineAnswer: "Python uses sqlite3 for SQLite database access.",
    candidateAnswer:
      "Python uses sqlite3 only after the telepathic compiler opens the database.",
    semanticScore: 0.29,
    keywordScore: 0.5,
    retrievalHit: true,
    latencyMs: 260,
    costUsd: 0.000004,
    chunks: [
      {
        rank: 1,
        docId: "python-sqlite3",
        text: "The sqlite3 module provides a DB-API interface for SQLite databases.",
        score: 0.97,
      },
      {
        rank: 2,
        docId: "python-json",
        text: "The json module encodes and decodes JSON documents.",
        score: 0.38,
      },
      {
        rank: 3,
        docId: "python-datetime",
        text: "The datetime module supplies classes for manipulating dates and times.",
        score: 0.27,
      },
    ],
  },
];

export const tracePagination: TracePagination = {
  total: 500,
  limit: 3,
  offset: 0,
  returned: 3,
};

export const tagBreakdown: TagBreakdownRow[] = [
  {
    tag: "hallucination_risk",
    baselineCaseCount: 180,
    candidateCaseCount: 180,
    candidateFailureCount: 180,
    candidatePassRate: 0,
  },
  {
    tag: "reasoning_required",
    baselineCaseCount: 170,
    candidateCaseCount: 170,
    candidateFailureCount: 170,
    candidatePassRate: 0,
  },
  {
    tag: "edge_case",
    baselineCaseCount: 150,
    candidateCaseCount: 150,
    candidateFailureCount: 150,
    candidatePassRate: 0,
  },
];

export const calibrationSignals: CalibrationSignal[] = [
  {
    evaluator: "Retrieval hit rate",
    pearson: 0.91,
    spearman: 0.88,
    agreementRate: 0.86,
    finding: "Preview signal on retrieval_required cases",
  },
  {
    evaluator: "Token F1 overlap",
    pearson: 0.78,
    spearman: 0.74,
    agreementRate: 0.72,
    finding: "Preview weakness on fluent hallucinations",
  },
  {
    evaluator: "Contains keywords",
    pearson: 0.69,
    spearman: 0.66,
    agreementRate: 0.68,
    finding: "Preview signal for exact-fact cases",
  },
];

export const scatterPoints: ScatterPoint[] = [
  { id: "p1", evaluatorScore: 0.94, humanLabel: 5, tag: "easy" },
  { id: "p2", evaluatorScore: 0.83, humanLabel: 4, tag: "retrieval_required" },
  { id: "p3", evaluatorScore: 0.61, humanLabel: 3, tag: "reasoning_required" },
  { id: "p4", evaluatorScore: 0.36, humanLabel: 1, tag: "hallucination_risk" },
  { id: "p5", evaluatorScore: 0.71, humanLabel: 2, tag: "edge_case" },
  { id: "p6", evaluatorScore: 0.28, humanLabel: 1, tag: "adversarial" },
  { id: "p7", evaluatorScore: 0.88, humanLabel: 5, tag: "easy" },
  { id: "p8", evaluatorScore: 0.56, humanLabel: 2, tag: "hallucination_risk" },
  { id: "p9", evaluatorScore: 0.79, humanLabel: 4, tag: "retrieval_required" },
  { id: "p10", evaluatorScore: 0.42, humanLabel: 2, tag: "reasoning_required" },
];

export const gateRules: GateRule[] = [
  {
    metric: "Pass rate",
    direction: "higher",
    tolerance: "2 percentage points",
    verdict: "fail",
  },
  {
    metric: "Token overlap",
    direction: "higher",
    tolerance: "0.02 score drop",
    verdict: "fail",
  },
  {
    metric: "p95 latency",
    direction: "lower",
    tolerance: "50ms slower",
    verdict: "fail",
  },
  {
    metric: "Mean cost",
    direction: "lower",
    tolerance: "20 percent increase",
    verdict: "pass",
  },
];
