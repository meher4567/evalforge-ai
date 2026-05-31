import pytest

from app.demo.scenario import run_demo_scenario


@pytest.mark.anyio
async def test_demo_scenario_runs_comparison_with_measured_summary():
    summary = await run_demo_scenario(case_count=20)

    assert summary["case_count"] == 20
    assert summary["baseline_status"] == "completed"
    assert summary["candidate_status"] == "completed"
    assert summary["gate_verdict"] == "fail"
    assert summary["metrics"]["pass_rate"]["baseline_point"] == 1.0
    assert summary["metrics"]["pass_rate"]["candidate_point"] < 1.0
