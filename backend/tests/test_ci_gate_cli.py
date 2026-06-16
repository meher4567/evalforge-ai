import json

import pytest

from app.cli import gate as gate_cli


def _payload(verdict: str = "fail", should_fail_ci: bool = True) -> dict:
    return {
        "comparison_id": "cmp-123",
        "baseline_run_id": "run-base",
        "candidate_run_id": "run-candidate",
        "verdict": verdict,
        "should_fail_ci": should_fail_ci,
        "dashboard_url": "http://localhost:5173",
        "generated_at": "2026-06-16T00:00:00+00:00",
        "metrics": [
            {
                "name": "pass_rate",
                "baseline": 1.0,
                "candidate": 0.82,
                "delta": -0.18,
                "delta_ci": [-0.22, -0.11],
                "status": "fail",
            }
        ],
        "gate_reasons": [{"metric": "pass_rate", "verdict": "fail"}],
        "markdown": "## EvalForge Deployment Gate\n\nGate verdict: `fail`\n",
    }


def test_gate_cli_writes_json_and_markdown_artifacts(monkeypatch, tmp_path):
    captured = {}

    def fake_fetch_ci_gate_report(**kwargs):
        captured.update(kwargs)
        return _payload()

    monkeypatch.setattr(gate_cli, "fetch_ci_gate_report", fake_fetch_ci_gate_report)
    json_out = tmp_path / "gate.json"
    markdown_out = tmp_path / "gate.md"

    exit_code = gate_cli.main(
        [
            "--base-url",
            "http://evalforge.internal:8000",
            "--comparison-id",
            "cmp-123",
            "--dashboard-url",
            "http://localhost:5173",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 1
    assert captured["base_url"] == "http://evalforge.internal:8000"
    assert captured["comparison_id"] == "cmp-123"
    assert captured["dashboard_url"] == "http://localhost:5173"
    assert json.loads(json_out.read_text(encoding="utf-8"))["verdict"] == "fail"
    assert markdown_out.read_text(encoding="utf-8").startswith("## EvalForge Deployment Gate")


def test_gate_cli_returns_zero_when_report_is_non_blocking(monkeypatch):
    monkeypatch.setattr(
        gate_cli,
        "fetch_ci_gate_report",
        lambda **_kwargs: _payload(verdict="warn", should_fail_ci=False),
    )

    exit_code = gate_cli.main(
        [
            "--base-url",
            "http://evalforge.internal:8000",
            "--comparison-id",
            "cmp-123",
        ]
    )

    assert exit_code == 0


def test_fetch_ci_gate_report_sends_auth_and_fail_on_warn(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return _payload(verdict="warn", should_fail_ci=True)

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, *, headers, params):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr(gate_cli.httpx, "Client", FakeClient)

    payload = gate_cli.fetch_ci_gate_report(
        base_url="http://evalforge.internal:8000/",
        comparison_id="cmp-123",
        api_key="secret",
        dashboard_url="http://localhost:5173",
        fail_on_warn=True,
        timeout_seconds=9.0,
    )

    assert payload["should_fail_ci"] is True
    assert captured["url"] == "http://evalforge.internal:8000/api/comparisons/cmp-123/ci-report"
    assert captured["headers"] == {"X-EvalForge-Api-Key": "secret"}
    assert captured["params"] == {
        "dashboard_url": "http://localhost:5173",
        "fail_on_warn": True,
    }
    assert captured["client_kwargs"] == {"timeout": 9.0}


def test_gate_cli_rejects_empty_base_url():
    with pytest.raises(SystemExit):
        gate_cli.main(["--base-url", "", "--comparison-id", "cmp-123"])
