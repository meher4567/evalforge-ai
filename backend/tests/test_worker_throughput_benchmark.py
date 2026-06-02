from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

worker_throughput = importlib.import_module("benchmarks.worker_throughput")
BenchmarkPayloadError = worker_throughput.BenchmarkPayloadError
build_summary = worker_throughput.build_summary


def test_build_summary_extracts_worker_throughput_from_dashboard_payload():
    dashboard_payload = {
        "benchmarkSummary": {
            "generatedAt": "2026-06-03T00:10:00+00:00",
            "benchmark": "latest_persisted_comparison",
            "caseCount": 50,
            "totalExecutions": 100,
            "elapsedSeconds": 2.057,
            "casesPerMinute": 2916.87,
            "gateVerdict": "fail",
        },
        "metrics": [
            {"key": "pass_rate", "baseline": 1.0, "candidate": 0.0},
            {"key": "semantic_similarity", "baseline": 1.0, "candidate": 0.284951},
        ],
    }

    summary = build_summary(
        dashboard_payload,
        case_count=50,
        worker_concurrency=4,
        environment="local_docker_desktop",
        source="docker_compose_seed",
    )

    assert summary["benchmark"] == "docker_celery_worker_throughput"
    assert summary["execution_mode"] == "celery"
    assert summary["source"] == "docker_compose_seed"
    assert summary["environment"] == "local_docker_desktop"
    assert summary["case_count"] == 50
    assert summary["total_executions"] == 100
    assert summary["worker_concurrency"] == 4
    assert summary["elapsed_seconds"] == 2.057
    assert summary["cases_per_minute"] == 2916.87
    assert summary["gate_verdict"] == "fail"
    assert summary["metrics"]["pass_rate"]["candidate"] == 0.0
    assert summary["metrics"]["semantic_similarity"]["candidate"] == pytest.approx(0.284951)
    assert (
        "docker compose exec backend uv run python -m app.cli.seed"
        in summary["reproduction_commands"][1]
    )


def test_build_summary_rejects_dashboard_payload_without_throughput_fields():
    with pytest.raises(BenchmarkPayloadError, match="benchmarkSummary.totalExecutions"):
        build_summary(
            {"benchmarkSummary": {"caseCount": 50}, "metrics": []},
            case_count=50,
            worker_concurrency=4,
            environment="local_docker_desktop",
            source="docker_compose_seed",
        )
