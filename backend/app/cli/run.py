"""
CLI command to run evals: ``evalforge run --suite demo --baseline v1 --candidate v2``

This is the developer-facing shortcut for running a complete eval cycle
(baseline → candidate → comparison) via direct DB access.

Usage:
    uv run python -m app.cli.run --suite demo-suite --baseline v1_baseline --candidate v2_candidate
    uv run python -m app.cli.run --sync --suite demo-suite --baseline v1 --candidate v2

In --sync mode, execution is in-process (dev/test/CI).
Without --sync (celery mode), runs are dispatched to Celery workers and the
CLI polls until completion before computing the comparison.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass

from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evalforge.cli.run")

POLL_INTERVAL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 300  # 5 minutes


@dataclass(frozen=True)
class RunResult:
    baseline_run_id: str
    candidate_run_id: str
    comparison_id: str
    gate_verdict: str
    gate_reasons: list[dict]


async def _poll_run_status(session, run_id: str, label: str) -> str:
    """Poll a run until it reaches a terminal status or timeout."""
    from app.models import EvalRun

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        await session.refresh(await session.get(EvalRun, run_id))
        run = await session.get(EvalRun, run_id)
        if run is None:
            raise RuntimeError(f"{label} run {run_id} disappeared from database")
        if run.status in ("completed", "partial", "failed"):
            logger.info(
                "%s run %s finished: status=%s completed=%d errored=%d",
                label,
                run_id,
                run.status,
                run.case_completed or 0,
                run.case_errored or 0,
            )
            return run.status
        logger.info(
            "%s run %s status=%s (polling…)",
            label,
            run_id,
            run.status,
        )
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"{label} run {run_id} did not complete within {POLL_TIMEOUT_SECONDS}s")


async def run_evals(
    suite_name: str,
    baseline_version_name: str,
    candidate_version_name: str,
    evaluator_config_name: str = "default-rag",
    gate_rule_name: str = "default-gates",
    sync_mode: bool = False,
) -> RunResult:
    """Run a complete eval cycle (baseline + candidate + comparison) via direct DB access."""
    from app.db.base import Base
    from app.db.session import async_session_factory
    from app.models import (
        AppVersion,
        EvalSuite,
        EvaluatorConfig,
        GateRule,
    )
    from app.services.comparison import DEFAULT_GATE_RULES, compute_comparison
    from app.services.run_dispatcher import dispatch_run
    from app.services.run_executor import execute_run

    engine = async_session_factory.kw["bind"]

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Look up entities by name
        suite = await session.scalar(select(EvalSuite).where(EvalSuite.name == suite_name))
        if suite is None:
            available = list(await session.scalars(select(EvalSuite.name)))
            logger.error("Suite '%s' not found. Available: %s", suite_name, available)
            sys.exit(1)

        baseline = await session.scalar(
            select(AppVersion).where(AppVersion.name == baseline_version_name)
        )
        if baseline is None:
            available = list(await session.scalars(select(AppVersion.name)))
            logger.error("Version '%s' not found. Available: %s", baseline_version_name, available)
            sys.exit(1)

        candidate = await session.scalar(
            select(AppVersion).where(AppVersion.name == candidate_version_name)
        )
        if candidate is None:
            available = list(await session.scalars(select(AppVersion.name)))
            logger.error("Version '%s' not found. Available: %s", candidate_version_name, available)
            sys.exit(1)

        eval_config = await session.scalar(
            select(EvaluatorConfig).where(EvaluatorConfig.name == evaluator_config_name)
        )
        if eval_config is None:
            available = list(await session.scalars(select(EvaluatorConfig.name)))
            logger.error(
                "Evaluator config '%s' not found. Available: %s",
                evaluator_config_name,
                available,
            )
            sys.exit(1)

        gate_rule = await session.scalar(select(GateRule).where(GateRule.name == gate_rule_name))
        if gate_rule is None:
            gate_rule = GateRule(name=gate_rule_name, rules=DEFAULT_GATE_RULES)
            session.add(gate_rule)
            await session.flush()

        # ── Execute baseline run ──
        logger.info(
            "Running baseline eval: version=%s suite=%s mode=%s",
            baseline.name,
            suite.name,
            "sync" if sync_mode else "celery",
        )
        if sync_mode:
            baseline_run = await execute_run(
                session,
                app_version_id=baseline.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
        else:
            baseline_run = await dispatch_run(
                session,
                app_version_id=baseline.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
            # Poll until worker completes
            await _poll_run_status(session, baseline_run.id, "Baseline")

        # ── Execute candidate run ──
        logger.info(
            "Running candidate eval: version=%s suite=%s mode=%s",
            candidate.name,
            suite.name,
            "sync" if sync_mode else "celery",
        )
        if sync_mode:
            candidate_run = await execute_run(
                session,
                app_version_id=candidate.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
        else:
            candidate_run = await dispatch_run(
                session,
                app_version_id=candidate.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
            # Poll until worker completes
            await _poll_run_status(session, candidate_run.id, "Candidate")

        # ── Compute comparison (only after both runs are terminal) ──
        logger.info(
            "Computing comparison: baseline=%s candidate=%s",
            baseline_run.id,
            candidate_run.id,
        )

        comparison, report = await compute_comparison(
            session,
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
        )

        await session.commit()

        return RunResult(
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
            comparison_id=comparison.id,
            gate_verdict=report.gate_verdict,
            gate_reasons=report.gate_reasons,
        )


def main():
    parser = argparse.ArgumentParser(
        description="EvalForge run: baseline → candidate → comparison",
    )
    parser.add_argument("--suite", required=True, help="Suite name (e.g., demo-suite)")
    parser.add_argument("--baseline", required=True, help="Baseline version name")
    parser.add_argument("--candidate", required=True, help="Candidate version name")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run in-process (no Celery). Default: Celery dispatch with polling.",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_evals(
            suite_name=args.suite,
            baseline_version_name=args.baseline,
            candidate_version_name=args.candidate,
            sync_mode=args.sync,
        )
    )

    print(
        json.dumps(
            {
                "baseline_run_id": result.baseline_run_id,
                "candidate_run_id": result.candidate_run_id,
                "comparison_id": result.comparison_id,
                "gate_verdict": result.gate_verdict,
                "gate_reasons": result.gate_reasons,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
