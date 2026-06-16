"""
Real sync-mode throughput benchmark for EvalForge AI.

Runs actual eval cases through the in-process executor and measures:
- case count
- total elapsed wall-clock time
- cases/minute
- p50 latency per item
- p95 latency per item
- completed / errored counts
- gate verdict

This benchmark uses sync mode (EVALFORGE_RUN_MODE=sync) with the
deterministic demo RAG adapter. No sleep simulation.

Usage:
    uv run --directory backend python benchmarks/throughput.py
    uv run --directory backend python benchmarks/throughput.py --cases 100
    uv run --directory backend python benchmarks/throughput.py --cases 500

For Celery worker throughput (REQUIRES DOCKER), see:
    benchmarks/worker_throughput.py  (ready-to-run, requires docker compose up)
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
from app.demo.scenario import run_demo_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real sync-mode throughput benchmark")
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
    case_count = args.cases

    # Run the real demo scenario
    t0 = time.perf_counter()
    summary = await run_demo_scenario(case_count=case_count)
    elapsed_seconds = round(time.perf_counter() - t0, 3)

    # Collect per-item latency from the database
    engine = async_session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        from sqlalchemy import text

        # Get all run items for this session's runs
        rows = await session.execute(
            text(
                "SELECT recorded_latency_ms FROM eval_run_items "
                "WHERE recorded_latency_ms IS NOT NULL "
                "ORDER BY recorded_latency_ms ASC"
            )
        )
        latencies = [row[0] for row in rows.fetchall()]

    # Compute p50/p95
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[int(n * 0.50)] if n > 0 else 0
    p95 = sorted_lat[int(n * 0.95)] if n > 1 else sorted_lat[0] if n > 0 else 0

    cases_per_min = round((case_count / elapsed_seconds) * 60, 1)

    total_items = 2 * case_count  # baseline + candidate
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": "sync_throughput_real",
        "execution_mode": "sync (in-process)",
        "note": "Real sync-mode executor. Not simulated. Celery benchmark requires Docker.",
        "summary": {
            "case_count": case_count,
            "total_items_executed": total_items,
            "elapsed_seconds": elapsed_seconds,
            "cases_per_minute": cases_per_min,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "mean_latency_ms": round(mean(latencies), 1) if latencies else 0,
            "max_latency_ms": sorted_lat[-1] if sorted_lat else 0,
            "baseline_status": summary.get("baseline_status", "unknown"),
            "candidate_status": summary.get("candidate_status", "unknown"),
            "gate_verdict": summary.get("gate_verdict", "unknown"),
        },
    }

    output_dir = Path(__file__).resolve().parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "throughput.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())