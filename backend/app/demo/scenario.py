from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.demo.dataset import build_demo_corpus, build_eval_cases
from app.models import App, AppVersion, EvalSuite, EvalSuiteCase, EvaluatorConfig
from app.models.entities import EvalCase
from app.services.comparison import compute_comparison
from app.services.run_executor import execute_run


async def run_demo_scenario(
    case_count: int = 500,
    database_url: str = "sqlite+aiosqlite:///:memory:",
) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    started = time.perf_counter()
    async with session_factory() as session:
        app = App(name="demo-rag", description="Deterministic RAG demo application")
        session.add(app)
        await session.flush()

        corpus = build_demo_corpus()
        baseline = AppVersion(
            app_id=app.id,
            name="v1_baseline",
            adapter_module="app.adapters.demo_rag",
            config={"top_k": 1, "corpus": corpus, "latency_ms": 120},
        )
        candidate = AppVersion(
            app_id=app.id,
            name="v2_hallucination_regression",
            adapter_module="app.adapters.demo_rag",
            config={
                "top_k": 1,
                "corpus": corpus,
                "failure_mode": "hallucinate",
                "latency_ms": 260,
            },
        )
        suite = EvalSuite(app_id=app.id, name="demo-rag-500")
        evaluator_config = EvaluatorConfig(
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
        session.add_all([baseline, candidate, suite, evaluator_config])
        await session.flush()

        for item in build_eval_cases(case_count):
            case = EvalCase(external_id=item["external_id"], payload=item["payload"])
            session.add(case)
            await session.flush()
            session.add(EvalSuiteCase(suite_id=suite.id, case_id=case.id))

        await session.commit()

        baseline_run = await execute_run(session, baseline.id, suite.id, evaluator_config.id)
        candidate_run = await execute_run(session, candidate.id, suite.id, evaluator_config.id)
        _comparison, report = await compute_comparison(session, baseline_run.id, candidate_run.id)

    elapsed_seconds = time.perf_counter() - started
    await engine.dispose()

    total_case_executions = case_count * 2
    return {
        "case_count": case_count,
        "total_case_executions": total_case_executions,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "cases_per_minute": round((total_case_executions / elapsed_seconds) * 60, 2),
        "baseline_status": baseline_run.status,
        "candidate_status": candidate_run.status,
        "gate_verdict": report.gate_verdict,
        "metrics": report.metrics,
        "gate_reasons": report.gate_reasons,
    }
