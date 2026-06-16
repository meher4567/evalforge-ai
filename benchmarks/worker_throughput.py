"""
Celery worker throughput benchmark for EvalForge AI.

REQUIRES DOCKER COMPOSE to be running:
    docker compose up --build
    docker compose exec backend uv run python benchmarks/worker_throughput.py --cases 100

This benchmark dispatches eval cases through Celery/Redis workers and measures:
- case count
- worker concurrency
- total elapsed wall-clock time (including queue wait)
- cases/minute
- p50 latency per item
- p95 latency per item
- completed / errored counts
- gate verdict

For sync mode benchmark (no Docker required), use:
    benchmarks/throughput.py

Docker worker concurrency levels:
    1 worker : docker compose up --scale worker=1
    2 workers: docker compose up --scale worker=2
    4 workers: docker compose up --scale worker=4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime, date
from pathlib import Path
from statistics import mean

import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db.base import Base
from app.db.session import async_session_factory
from app.models import AppVersion, EvalSuite, EvaluatorConfig, GateRule
from app.services.comparison import DEFAULT_GATE_RULES, compute_comparison
from app.services.run_dispatcher import dispatch_run
from app.demo.dataset import build_demo_corpus, build_eval_cases
from app.models import (
    App,
    AppVersion,
    EvalCase,
    EvalSuite,
    EvalSuiteCase,
    EvaluatorConfig,
    GateRule,
)
from app.db.base import new_uuid


async def _poll_run(session, run_id: str, label: str, timeout: int = 600) -> str:
    """Poll until run is terminal."""
    from app.models import EvalRun

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = await session.get(EvalRun, run_id)
        if run is None:
            raise RuntimeError(f"{label} run disappeared")
        if run.status in ("completed", "partial", "failed"):
            return run.status
        await asyncio.sleep(1.0)
    raise TimeoutError(f"{label} run timed out")


async def run_worker_benchmark(case_count: int = 500, output_dir: Path | None = None) -> dict:
    """
    Run a real Celery-dispatched benchmark.

    Seeds a project, dispatches baseline + candidate runs,
    polls for completion, computes comparison, measures latencies.
    """
    engine = async_session_factory.kw["bind"]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Seed minimal project
        app = App(id=new_uuid(), name="benchmark-rag", description="Worker benchmark")
        session.add(app)

        eval_config = EvaluatorConfig(
            id=new_uuid(),
            name="benchmark-config",
            config={
                "evaluators": [
                    {"name": "contains_keywords", "threshold": 0.8},
                    {"name": "semantic_similarity", "threshold": 0.5},
                    {"name": "forbidden_claim"},
                ]
            },
        )
        session.add(eval_config)

        gate_rule = GateRule(id=new_uuid(), name="benchmark-gates", rules=DEFAULT_GATE_RULES)
        session.add(gate_rule)

        corpus = build_demo_corpus()
        baseline_version = AppVersion(
            id=new_uuid(),
            app_id=app.id,
            name="v1_baseline",
            adapter_module="app.adapters.demo_rag",
            config={"top_k": 3, "corpus": corpus, "latency_ms": 120},
        )
        session.add(baseline_version)

        candidate_version = AppVersion(
            id=new_uuid(),
            app_id=app.id,
            name="v2_candidate",
            adapter_module="app.adapters.demo_rag",
            config={
                "top_k": 3,
                "corpus": corpus,
                "latency_ms": 260,
                "failure_mode": "hallucinate",
            },
        )
        session.add(candidate_version)

        suite = EvalSuite(id=new_uuid(), app_id=app.id, name="benchmark-suite")
        session.add(suite)
        await session.flush()

        cases = build_eval_cases(case_count)
        for case_data in cases:
            case = EvalCase(
                id=new_uuid(),
                external_id=case_data["external_id"],
                payload=case_data["payload"],
            )
            session.add(case)
            await session.flush()
            session.add(EvalSuiteCase(suite_id=suite.id, case_id=case.id))

        await session.commit()

        # ── Dispatch baseline ──
        t0 = time.perf_counter()
        baseline_run = await dispatch_run(
            session,
            app_version_id=baseline_version.id,
            suite_id=suite.id,
            evaluator_config_id=eval_config.id,
        )
        await _poll_run(session, baseline_run.id, "Baseline")

        # ── Dispatch candidate ──
        candidate_run = await dispatch_run(
            session,
            app_version_id=candidate_version.id,
            suite_id=suite.id,
            evaluator_config_id=eval_config.id,
        )
        await _poll_run(session, candidate_run.id, "Candidate")

        elapsed_seconds = round(time.perf_counter() - t0, 3)

        # ── Compute comparison ──
        comparison, report = await compute_comparison(
            session,
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
        )
        await session.commit()

        # ── Collect latency data ──
        from sqlalchemy import text

        rows = await session.execute(
            text(
                "SELECT recorded_latency_ms FROM eval_run_items "
                "WHERE recorded_latency_ms IS NOT NULL "
                "ORDER BY recorded_latency_ms ASC"
            )
        )
        latencies = [row[0] for row in rows.fetchall()]
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        p50 = sorted_lat[int(n * 0.50)] if n > 0 else 0
        p95 = sorted_lat[int(n * 0.95)] if n > 1 else sorted_lat[0] if n > 0 else 0

        total_items = 2 * case_count
        result = {
            "generated_at": datetime.now(UTC).isoformat(),
            "benchmark": "celery_worker_throughput",
            "execution_mode": "celery (docker compose)",
            "summary": {
                "case_count": case_count,
                "total_items_executed": total_items,
                "elapsed_seconds": elapsed_seconds,
                "cases_per_minute": round((case_count / elapsed_seconds) * 60, 1),
                "p50_latency_ms": p50,
                "p95_latency_ms": p95,
                "mean_latency_ms": round(mean(latencies), 1) if latencies else 0,
                "maximum_latency_ms": sorted_lat[-1] if sorted_lat else 0,
                "baseline_status": baseline_run.status,
                "candidate_status": candidate_run.status,
                "gate_verdict": report.gate_verdict,
            },
        }

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / "worker_throughput.json"
            out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"Wrote {out_path}")

        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Celery worker throughput benchmark (REQUIRES DOCKER)"
    )
    parser.add_argument(
        "--cases", type=int, default=500, help="Number of eval cases (default: 500)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results") / str(date.today()),
        help="Output directory for benchmark JSON",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await run_worker_benchmark(case_count=args.cases, output_dir=args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())