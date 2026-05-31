from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.demo.scenario import run_demo_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deterministic EvalForge demo benchmark.")
    parser.add_argument("--cases", type=int, default=500, help="Number of eval cases to generate.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../benchmarks/results/2026-05-31"),
        help="Directory where the JSON benchmark result is written.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    summary = await run_demo_scenario(case_count=args.cases)
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": "deterministic_demo_rag_regression",
        "reproduction_command": (
            f"uv run --directory backend python ../benchmarks/run_demo.py --cases {args.cases}"
        ),
        "summary": summary,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "demo_results.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
