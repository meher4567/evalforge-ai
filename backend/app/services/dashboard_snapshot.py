from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_RESULT_PATH = PROJECT_ROOT / "benchmarks" / "results" / "2026-05-31" / "demo_results.json"


def load_demo_dashboard_snapshot() -> dict[str, Any]:
    benchmark = _load_benchmark_result()
    summary = benchmark["summary"]
    metrics = summary["metrics"]

    return {
        "benchmarkSummary": {
            "generatedAt": benchmark["generated_at"],
            "benchmark": benchmark["benchmark"],
            "reproductionCommand": benchmark["reproduction_command"],
            "caseCount": summary["case_count"],
            "totalExecutions": summary["total_case_executions"],
            "elapsedSeconds": summary["elapsed_seconds"],
            "casesPerMinute": summary["cases_per_minute"],
            "gateVerdict": summary["gate_verdict"],
        },
        "metrics": _build_metrics(metrics),
        "runs": _build_runs(metrics),
        "traceCases": _build_trace_cases(),
        "tracePagination": _build_trace_pagination(),
        "tagBreakdown": _build_tag_breakdown(),
        "gateRules": _build_gate_rules(),
    }


def _load_benchmark_result() -> dict[str, Any]:
    with BENCHMARK_RESULT_PATH.open(encoding="utf-8") as benchmark_file:
        return json.load(benchmark_file)


def _build_metrics(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    metric_specs = [
        ("pass_rate", "Pass rate", "Pass", "%", "higher", 0.02),
        ("semantic_similarity", "Token overlap", "Overlap", "score", "higher", 0.02),
        ("p95_latency_ms", "p95 latency", "p95", "ms", "lower", 50.0),
        ("cost_mean_usd", "Mean cost", "Cost", "usd", "lower", 0.2),
    ]

    return [
        {
            "key": key,
            "label": label,
            "shortLabel": short_label,
            "unit": unit,
            "baseline": metrics[key]["baseline_point"],
            "candidate": metrics[key]["candidate_point"],
            "baselineCi": [metrics[key]["baseline_ci_lower"], metrics[key]["baseline_ci_upper"]],
            "candidateCi": [metrics[key]["candidate_ci_lower"], metrics[key]["candidate_ci_upper"]],
            "delta": metrics[key]["delta_point"],
            "deltaCi": [metrics[key]["delta_ci_lower"], metrics[key]["delta_ci_upper"]],
            "direction": direction,
            "tolerance": tolerance,
            "status": _metric_status(key),
        }
        for key, label, short_label, unit, direction, tolerance in metric_specs
    ]


def _metric_status(metric_key: str) -> str:
    return "pass" if metric_key == "cost_mean_usd" else "fail"


def _build_runs(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "run_candidate_500",
            "version": "v2_candidate_hallucination_injected",
            "suite": "demo_rag_500",
            "cases": 500,
            "passRate": metrics["pass_rate"]["candidate_point"],
            "semanticSimilarity": metrics["semantic_similarity"]["candidate_point"],
            "p95LatencyMs": metrics["p95_latency_ms"]["candidate_point"],
            "costMeanUsd": metrics["cost_mean_usd"]["candidate_point"],
            "createdAt": "2026-05-31 18:00 IST",
            "status": "completed",
        },
        {
            "id": "run_baseline_500",
            "version": "v1_baseline_bge_top3",
            "suite": "demo_rag_500",
            "cases": 500,
            "passRate": metrics["pass_rate"]["baseline_point"],
            "semanticSimilarity": metrics["semantic_similarity"]["baseline_point"],
            "p95LatencyMs": metrics["p95_latency_ms"]["baseline_point"],
            "costMeanUsd": metrics["cost_mean_usd"]["baseline_point"],
            "createdAt": "2026-05-31 17:59 IST",
            "status": "completed",
        },
        {
            "id": "run_prompt_rewrite_100",
            "version": "v3_prompt_rewrite_preview",
            "suite": "demo_rag_100",
            "cases": 100,
            "passRate": 0.94,
            "semanticSimilarity": 0.91,
            "p95LatencyMs": 188,
            "costMeanUsd": 0.000005,
            "createdAt": "2026-05-30 22:18 IST",
            "status": "completed",
        },
        {
            "id": "run_flaky_subset",
            "version": "v1_baseline_rerun_n5",
            "suite": "flaky_subset_50",
            "cases": 250,
            "passRate": 0.972,
            "semanticSimilarity": 0.956,
            "p95LatencyMs": 142,
            "costMeanUsd": 0.000004,
            "createdAt": "2026-05-30 20:41 IST",
            "status": "partial",
        },
    ]


def _build_trace_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "demo-0001",
            "tag": "hallucination_risk",
            "evaluator": "token_f1_overlap",
            "reason": "Candidate answered with forbidden synthetic claim",
            "question": "Which Python module is used for venv?",
            "expected": "Python uses the venv module for virtual environments.",
            "baselineAnswer": "Python uses the venv module for virtual environments.",
            "candidateAnswer": (
                "Python uses a telepathic compiler backed by a quantum database for venv."
            ),
            "semanticScore": 0.25,
            "keywordScore": 0,
            "retrievalHit": True,
            "latencyMs": 260,
            "costUsd": 0.000004,
            "chunks": [
                {
                    "rank": 1,
                    "docId": "python-venv",
                    "text": "The venv module creates lightweight Python virtual environments.",
                    "score": 0.96,
                },
                {
                    "rank": 2,
                    "docId": "python-pathlib",
                    "text": "The pathlib module represents filesystem paths as objects.",
                    "score": 0.44,
                },
                {
                    "rank": 3,
                    "docId": "python-unittest",
                    "text": "The unittest module supports test automation and shared setup code.",
                    "score": 0.39,
                },
            ],
        },
        {
            "id": "demo-0007",
            "tag": "reasoning_required",
            "evaluator": "contains_keywords",
            "reason": "Expected facts were missing from the generated answer",
            "question": "Which Python module is used for asyncio?",
            "expected": "Python uses asyncio for async concurrency.",
            "baselineAnswer": "Python uses asyncio for async concurrency.",
            "candidateAnswer": (
                "Python uses a quantum database for async code and does not need modules."
            ),
            "semanticScore": 0.31,
            "keywordScore": 0,
            "retrievalHit": True,
            "latencyMs": 260,
            "costUsd": 0.000004,
            "chunks": [
                {
                    "rank": 1,
                    "docId": "python-asyncio",
                    "text": (
                        "The asyncio module supports concurrent code with async and await syntax."
                    ),
                    "score": 0.94,
                },
                {
                    "rank": 2,
                    "docId": "python-logging",
                    "text": "The logging module provides flexible event logging for applications.",
                    "score": 0.35,
                },
                {
                    "rank": 3,
                    "docId": "python-json",
                    "text": "The json module encodes and decodes JSON documents.",
                    "score": 0.32,
                },
            ],
        },
        {
            "id": "demo-0010",
            "tag": "edge_case",
            "evaluator": "forbidden_claim",
            "reason": "Forbidden claim matched the generated answer",
            "question": "Which Python module is used for sqlite3?",
            "expected": "Python uses sqlite3 for SQLite database access.",
            "baselineAnswer": "Python uses sqlite3 for SQLite database access.",
            "candidateAnswer": (
                "Python uses sqlite3 only after the telepathic compiler opens the database."
            ),
            "semanticScore": 0.29,
            "keywordScore": 0.5,
            "retrievalHit": True,
            "latencyMs": 260,
            "costUsd": 0.000004,
            "chunks": [
                {
                    "rank": 1,
                    "docId": "python-sqlite3",
                    "text": "The sqlite3 module provides a DB-API interface for SQLite databases.",
                    "score": 0.97,
                },
                {
                    "rank": 2,
                    "docId": "python-json",
                    "text": "The json module encodes and decodes JSON documents.",
                    "score": 0.38,
                },
                {
                    "rank": 3,
                    "docId": "python-datetime",
                    "text": (
                        "The datetime module supplies classes for manipulating dates and times."
                    ),
                    "score": 0.27,
                },
            ],
        },
    ]


def _build_trace_pagination() -> dict[str, int]:
    return {
        "total": 500,
        "limit": 3,
        "offset": 0,
        "returned": 3,
    }


def _build_tag_breakdown() -> list[dict[str, Any]]:
    return [
        {
            "tag": "hallucination_risk",
            "baselineCaseCount": 180,
            "candidateCaseCount": 180,
            "candidateFailureCount": 180,
            "candidatePassRate": 0.0,
        },
        {
            "tag": "reasoning_required",
            "baselineCaseCount": 170,
            "candidateCaseCount": 170,
            "candidateFailureCount": 170,
            "candidatePassRate": 0.0,
        },
        {
            "tag": "edge_case",
            "baselineCaseCount": 150,
            "candidateCaseCount": 150,
            "candidateFailureCount": 150,
            "candidatePassRate": 0.0,
        },
    ]


def _build_gate_rules() -> list[dict[str, str]]:
    return [
        {
            "metric": "Pass rate",
            "direction": "higher",
            "tolerance": "2 percentage points",
            "verdict": "fail",
        },
        {
            "metric": "Token overlap",
            "direction": "higher",
            "tolerance": "0.02 score drop",
            "verdict": "fail",
        },
        {
            "metric": "p95 latency",
            "direction": "lower",
            "tolerance": "50ms slower",
            "verdict": "fail",
        },
        {
            "metric": "Mean cost",
            "direction": "lower",
            "tolerance": "20 percent increase",
            "verdict": "pass",
        },
    ]
