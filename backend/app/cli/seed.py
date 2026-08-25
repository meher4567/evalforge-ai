"""
Seed command: creates a complete demo project with apps, versions, suites, cases,
evaluator configs, runs, comparison, and regression report.

Usage:
    uv run python -m app.cli.seed                          # sync mode (dev)
    uv run python -m app.cli.seed --cases 100
    uv run python -m app.cli.seed --mode celery --cases 500  # with worker proof
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

from app.db.base import new_uuid
from app.db.session import SessionLocal
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
from app.services.comparison import DEFAULT_GATE_RULES, compute_comparison
from app.services.run_executor import execute_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evalforge.seed")

POLL_INTERVAL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 600  # 10 minutes for large seeds


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


async def seed_everything(case_count: int = 500, run_mode: str = "sync") -> dict:
    """
    Seed the database with a complete demo project and return a summary dict.

    Args:
        case_count: Number of eval cases to generate.
        run_mode: "sync" = in-process execution (dev/test).
                  "celery" = dispatch to Celery workers and poll (Docker proof).
    """
    if run_mode not in ("sync", "celery"):
        raise ValueError(f"Invalid run_mode: {run_mode}. Must be 'sync' or 'celery'.")

    async with SessionLocal() as session:
        # 1. Create app
        app = App(id=new_uuid(), name="demo-rag", description="Demo RAG evaluation app")
        session.add(app)

        # 2. Create evaluator config
        eval_config = EvaluatorConfig(
            id=new_uuid(),
            name="default-rag",
            config={
                "evaluators": [
                    {"name": "contains_keywords", "threshold": 0.8},
                    {"name": "token_f1_overlap", "threshold": 0.5},
                    {"name": "retrieval_hit_rate"},
                    {"name": "forbidden_claim"},
                    {"name": "latency_threshold", "threshold_ms": 200},
                    {"name": "cost_threshold", "threshold_usd": 0.01},
                ]
            },
        )
        session.add(eval_config)

        # 3. Create gate rule
        gate_rule = GateRule(
            id=new_uuid(),
            name="default-gates",
            rules=DEFAULT_GATE_RULES,
        )
        session.add(gate_rule)

        # 4. Create baseline version
        corpus = build_demo_corpus()
        baseline_version = AppVersion(
            id=new_uuid(),
            app_id=app.id,
            name="v1_baseline",
            adapter_module="app.adapters.demo_rag",
            config={"top_k": 3, "corpus": corpus, "latency_ms": 120},
        )
        session.add(baseline_version)

        # 5. Create candidate version (hallucination-injected)
        candidate_version = AppVersion(
            id=new_uuid(),
            app_id=app.id,
            name="v2_candidate_hallucination",
            adapter_module="app.adapters.demo_rag",
            config={
                "top_k": 3,
                "corpus": corpus,
                "latency_ms": 260,
                "failure_mode": "hallucinate",
            },
        )
        session.add(candidate_version)

        # 6. Create suite and import cases
        suite = EvalSuite(id=new_uuid(), app_id=app.id, name="demo-suite")
        session.add(suite)
        await session.flush()

        cases = build_eval_cases(case_count)
        logger.info("Importing %d eval cases", len(cases))

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

        # 7. Run baseline evaluation
        logger.info(
            "Running baseline evaluation (%d cases, mode=%s)",
            case_count,
            run_mode,
        )
        if run_mode == "sync":
            baseline_run = await execute_run(
                session,
                app_version_id=baseline_version.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
        else:
            from app.services.run_dispatcher import dispatch_run

            baseline_run = await dispatch_run(
                session,
                app_version_id=baseline_version.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
            await _poll_run_status(session, baseline_run.id, "Baseline")

        # 8. Run candidate evaluation
        logger.info(
            "Running candidate evaluation (%d cases, mode=%s)",
            case_count,
            run_mode,
        )
        if run_mode == "sync":
            candidate_run = await execute_run(
                session,
                app_version_id=candidate_version.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
        else:
            from app.services.run_dispatcher import dispatch_run

            candidate_run = await dispatch_run(
                session,
                app_version_id=candidate_version.id,
                suite_id=suite.id,
                evaluator_config_id=eval_config.id,
            )
            await _poll_run_status(session, candidate_run.id, "Candidate")

        # 9. Compute comparison using the real service (validates both runs terminal)
        logger.info("Computing comparison")
        comparison, report = await compute_comparison(
            session,
            baseline_run_id=baseline_run.id,
            candidate_run_id=candidate_run.id,
        )
        await session.commit()

        summary = {
            "case_count": case_count,
            "run_mode": run_mode,
            "baseline_status": baseline_run.status,
            "candidate_status": candidate_run.status,
            "gate_verdict": report.gate_verdict,
            "metrics": {
                "pass_rate": {
                    "baseline_point": report.metrics["pass_rate"]["baseline_point"],
                    "candidate_point": report.metrics["pass_rate"]["candidate_point"],
                },
                "semantic_similarity": {
                    "baseline_point": report.metrics["semantic_similarity"]["baseline_point"],
                    "candidate_point": report.metrics["semantic_similarity"]["candidate_point"],
                },
            },
        }
        logger.info("Seed complete: %s", json.dumps(summary, indent=2))
        return summary


def main():
    parser = argparse.ArgumentParser(description="Seed EvalForge with demo data")
    parser.add_argument(
        "--cases", type=int, default=500, help="Number of eval cases (default: 500)"
    )
    parser.add_argument(
        "--mode",
        choices=["sync", "celery"],
        default="sync",
        help="Execution mode: sync (in-process, default) or celery (worker pool + polling)",
    )
    args = parser.parse_args()
    asyncio.run(seed_everything(case_count=args.cases, run_mode=args.mode))


if __name__ == "__main__":
    main()
