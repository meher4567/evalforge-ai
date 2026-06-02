from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


class BenchmarkPayloadError(ValueError):
    """Raised when the dashboard payload cannot produce a benchmark artifact."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Docker/Celery worker throughput from the latest dashboard snapshot."
    )
    parser.add_argument("--cases", type=int, default=50, help="Eval cases per app version.")
    parser.add_argument(
        "--worker-concurrency",
        type=int,
        default=4,
        help="Celery worker concurrency used for the measurement.",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/dashboard/latest",
        help="Dashboard endpoint to read after the Celery seed run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks") / "results" / date.today().isoformat(),
        help="Directory where worker_throughput.json is written.",
    )
    parser.add_argument(
        "--environment",
        default="local_docker_desktop",
        help="Short environment label for the measurement.",
    )
    parser.add_argument(
        "--source",
        default="docker_compose_seed",
        help="Short label describing how the measurement was produced.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Read the current dashboard snapshot without running the Docker seed command.",
    )
    return parser.parse_args()


def fetch_dashboard(api_url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(api_url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not fetch dashboard snapshot from {api_url}") from exc


def build_summary(
    dashboard_payload: dict[str, Any],
    *,
    case_count: int,
    worker_concurrency: int,
    environment: str,
    source: str,
) -> dict[str, Any]:
    benchmark_summary = _required_dict(dashboard_payload, "benchmarkSummary")
    metrics = _metrics_by_key(dashboard_payload.get("metrics", []))
    seed_command = (
        "docker compose exec backend uv run python -m app.cli.seed "
        f"--mode celery --cases {case_count}"
    )

    dashboard_case_count = _required_value(benchmark_summary, "benchmarkSummary.caseCount")
    if dashboard_case_count != case_count:
        raise BenchmarkPayloadError(
            "benchmarkSummary.caseCount does not match requested case count "
            f"({dashboard_case_count} != {case_count})"
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": "docker_celery_worker_throughput",
        "execution_mode": "celery",
        "environment": environment,
        "source": source,
        "case_count": case_count,
        "total_executions": _required_value(
            benchmark_summary,
            "benchmarkSummary.totalExecutions",
        ),
        "worker_concurrency": worker_concurrency,
        "elapsed_seconds": _required_value(
            benchmark_summary,
            "benchmarkSummary.elapsedSeconds",
        ),
        "cases_per_minute": _required_value(
            benchmark_summary,
            "benchmarkSummary.casesPerMinute",
        ),
        "gate_verdict": _required_value(benchmark_summary, "benchmarkSummary.gateVerdict"),
        "metrics": metrics,
        "reproduction_commands": [
            "docker compose up --build -d",
            seed_command,
            "curl http://localhost:8000/api/dashboard/latest",
            "docker compose logs worker --tail 100",
        ],
        "limitations": [
            "Measured with the deterministic demo adapter, not an external LLM provider.",
            "Local Docker throughput is a smoke benchmark, not a production capacity claim.",
            "The rate includes eval pipeline overhead for this seeded workload.",
        ],
    }


def write_summary(summary: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "worker_throughput.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return output_path


def run_seed(case_count: int) -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "backend",
        "uv",
        "run",
        "python",
        "-m",
        "app.cli.seed",
        "--mode",
        "celery",
        "--cases",
        str(case_count),
    ]
    subprocess.run(command, check=True)


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise BenchmarkPayloadError(f"Missing dashboard field: {key}")
    return value


def _required_value(payload: dict[str, Any], dotted_key: str) -> Any:
    field_name = dotted_key.rsplit(".", maxsplit=1)[-1]
    if field_name not in payload:
        raise BenchmarkPayloadError(f"Missing dashboard field: {dotted_key}")
    return payload[field_name]


def _metrics_by_key(metrics_payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(metrics_payload, list):
        raise BenchmarkPayloadError("Dashboard metrics must be a list")

    metrics: dict[str, dict[str, Any]] = {}
    for metric in metrics_payload:
        if not isinstance(metric, dict) or "key" not in metric:
            continue
        metrics[str(metric["key"])] = {
            "baseline": metric.get("baseline"),
            "candidate": metric.get("candidate"),
            "delta": metric.get("delta"),
            "status": metric.get("status"),
        }
    return metrics


def main() -> None:
    args = parse_args()
    if not args.skip_seed:
        run_seed(args.cases)

    dashboard = fetch_dashboard(args.api_url)
    summary = build_summary(
        dashboard,
        case_count=args.cases,
        worker_concurrency=args.worker_concurrency,
        environment=args.environment,
        source=args.source,
    )
    output_path = write_summary(summary, args.output_dir)
    print(f"Wrote {output_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
