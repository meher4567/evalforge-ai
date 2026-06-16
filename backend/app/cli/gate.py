from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx


def fetch_ci_gate_report(
    *,
    base_url: str,
    comparison_id: str,
    api_key: str | None = None,
    dashboard_url: str | None = None,
    fail_on_warn: bool = False,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    normalized_base_url = base_url.rstrip("/")
    url = f"{normalized_base_url}/api/comparisons/{comparison_id}/ci-report"
    headers = {"X-EvalForge-Api-Key": api_key} if api_key else {}
    params: dict[str, Any] = {"fail_on_warn": fail_on_warn}
    if dashboard_url:
        params["dashboard_url"] = dashboard_url

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


def write_artifacts(
    payload: dict[str, Any],
    *,
    json_out: str | None = None,
    markdown_out: str | None = None,
) -> None:
    if json_out:
        Path(json_out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if markdown_out:
        Path(markdown_out).write_text(payload["markdown"], encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch an EvalForge comparison gate report and return a CI exit code.",
    )
    parser.add_argument("--base-url", required=True, help="EvalForge API base URL")
    parser.add_argument("--comparison-id", required=True, help="Comparison ID to check")
    parser.add_argument("--api-key", help="Optional EvalForge API key")
    parser.add_argument("--dashboard-url", help="Optional dashboard URL for the Markdown report")
    parser.add_argument("--json-out", help="Optional JSON artifact path")
    parser.add_argument("--markdown-out", help="Optional Markdown artifact path")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat warning verdicts as CI failures.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    args = parser.parse_args(argv)

    if not args.base_url.strip():
        parser.error("--base-url must not be empty")

    payload = fetch_ci_gate_report(
        base_url=args.base_url,
        comparison_id=args.comparison_id,
        api_key=args.api_key,
        dashboard_url=args.dashboard_url,
        fail_on_warn=args.fail_on_warn,
        timeout_seconds=args.timeout_seconds,
    )
    write_artifacts(payload, json_out=args.json_out, markdown_out=args.markdown_out)
    print(payload["markdown"])
    return 1 if payload["should_fail_ci"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
