from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.flakiness import classify_flaky_cases, summarize_flakiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic flaky-eval benchmark.")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    observations = build_synthetic_flaky_observations()
    classifications = classify_flaky_cases(observations)
    summary = summarize_flakiness(classifications)

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": "deterministic_flaky_eval_detection",
        "protocol": {
            "reruns_per_case": 5,
            "stable_stddev_lt": 0.05,
            "flaky_stddev_gte": 0.05,
            "flaky_stddev_lt": 0.20,
            "inconclusive_stddev_gte": 0.20,
        },
        "summary": asdict(summary),
        "classifications": {
            case_id: asdict(classification)
            for case_id, classification in classifications.items()
        },
    }

    out_dir = args.out_dir or PROJECT_ROOT / "benchmarks" / "results" / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "flaky_eval_results.json"
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path.relative_to(PROJECT_ROOT)}")
    print(json.dumps(output["summary"], indent=2))


def build_synthetic_flaky_observations() -> dict[str, list[float]]:
    observations: dict[str, list[float]] = {}

    for index in range(25):
        base = 0.86 + (index % 4) * 0.01
        observations[f"stable-{index + 1:03d}"] = [
            base,
            base + 0.01,
            base - 0.01,
            base + 0.005,
            base - 0.005,
        ]

    for index in range(15):
        base = 0.72 + (index % 3) * 0.02
        observations[f"flaky-{index + 1:03d}"] = [
            base,
            base + 0.11,
            base - 0.08,
            base + 0.05,
            base - 0.03,
        ]

    for index in range(10):
        base = 0.52 + (index % 2) * 0.04
        observations[f"inconclusive-{index + 1:03d}"] = [
            base,
            0.98,
            0.15,
            base + 0.21,
            base - 0.19,
        ]

    return observations


if __name__ == "__main__":
    main()
