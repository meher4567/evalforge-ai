# Interview Defense Guide

This guide is written for explaining EvalForge as if you built it line by line. Use it after reading the code once; it gives you the story and the important questions interviewers may ask.

## One-Minute Explanation

EvalForge AI is a regression testing platform for RAG and LLM apps. Normal unit tests do not catch prompt and retriever regressions well, so EvalForge runs an eval suite against a baseline version and a candidate version, stores every trace, scores every output with multiple evaluators, and decides whether the candidate should pass, warn, or fail based on quality, latency, and cost gates.

The default demo is deterministic and free-tier friendly. It does not depend on paid model APIs. The benchmark intentionally injects a bad candidate so the gate catches the regression.

## What Makes It More Than CRUD

The hard parts are:

- versioned eval runs
- immutable eval cases
- per-case traces
- evaluator engine with multiple scoring strategies
- skipped and errored evaluator handling
- bootstrap confidence intervals
- gate rules that combine multiple metrics
- trace-level debugging UI
- honest calibration methodology

CRUD is only the registry layer. The value is in comparing outputs and explaining failures.

## File Map

Backend:

- `backend/app/main.py`: FastAPI app assembly.
- `backend/app/models/entities.py`: database entities and relationships.
- `backend/app/api/apps.py`: app, version, and suite APIs.
- `backend/app/api/suites.py`: eval case import and suite summary APIs.
- `backend/app/api/runs.py`: run execution and trace retrieval APIs.
- `backend/app/api/comparisons.py`: comparison and gate decision APIs.
- `backend/app/api/dashboard.py`: dashboard snapshot API.
- `backend/app/services/dashboard_aggregation.py`: database-backed latest comparison snapshot.
- `backend/app/adapters/demo_rag.py`: deterministic RAG-style demo adapter.
- `backend/app/evaluators/`: evaluator contracts and implementations.
- `backend/app/services/run_executor.py`: run execution orchestration.
- `backend/app/services/comparison.py`: metric aggregation and gate verdicts.
- `backend/app/services/statistics.py`: bootstrap confidence intervals.
- `backend/app/services/flakiness.py`: repeated-score flaky case classification.
- `backend/app/services/calibration.py`: calibration metrics.

Frontend:

- `frontend/src/App.tsx`: app shell, navigation, selected run, selected trace, filters.
- `frontend/src/data/demo.ts`: measured benchmark-backed demo data.
- `frontend/src/components/MetricCard.tsx`: point estimates and confidence intervals.
- `frontend/src/components/ComparisonBars.tsx`: baseline vs candidate visual comparison.
- `frontend/src/components/RunsTable.tsx`: run history.
- `frontend/src/components/TraceInspector.tsx`: failure explanation.
- `frontend/src/components/CalibrationPanel.tsx`: calibration preview.

Benchmarks:

- `benchmarks/run_demo.py`: creates the demo scenario, runs baseline and candidate, writes results JSON.
- `benchmarks/results/2026-05-31/demo_results.json`: measured benchmark output.

Docs:

- `TECHNICAL_DESIGN.md`: deep architecture.
- `BUILD_PLAN.md`: A- target plan and acceptance criteria.
- `docs/phase-5-dashboard-design.md`: frontend design and verification.
- `docs/project-status.md`: honest current phase status.
- `docs/labeling_rubric.md`: calibration labeling rules.
- `docs/calibration_findings.md`: current calibration status.

## Core Concepts To Explain

### Eval Case

An eval case is an input plus expected facts, expected output, forbidden claims, tags, and retrieval targets. Cases should be immutable once used in a run, otherwise historical pass rates become meaningless.

### App Version

An app version is a snapshot of a prompt, model, retriever settings, adapter module, and config. Baseline and candidate comparisons are comparisons between two completed runs, not between mutable configs.

### Trace

A trace is the evidence for one case execution:

- input
- retrieved chunks
- prompt or adapter steps
- answer
- model metadata
- latency and cost
- evaluator scores

The trace viewer exists so failures are explainable.

### Evaluator

An evaluator is a scoring function over a case and output. Examples:

- exact match
- contains expected facts
- semantic similarity
- retrieval hit rate
- forbidden claim detection
- latency threshold
- cost threshold

Each evaluator returns score, pass/fail, skipped/error state, and details.

### Bootstrap CI

A point estimate can lie. If pass rate changes by 1%, that might just be sampling noise. Bootstrap resampling estimates a confidence interval by repeatedly resampling the cases and recomputing the metric.

In the comparison gate, a candidate fails when the CI shows a regression beyond tolerance.

### Gate Rule

A gate rule says:

- which metric matters
- whether higher or lower is better
- how much regression is tolerated
- what severity to apply

The final verdict is the worst metric verdict.

### Flaky Eval

A flaky eval case has unstable scores across repeated runs. EvalForge computes standard deviation across repeated scores and marks cases as stable, flaky, or inconclusive. Flaky and inconclusive cases should not drive hard gate failures.

## Likely Interview Questions

### Why not just manually test a few prompts?

Manual prompt testing is not repeatable and misses regressions. EvalForge runs hundreds of cases and stores every trace, so the result is measurable and debuggable.

### Why use multiple evaluators?

Different failures need different evaluators. Exact match catches strict fact extraction. Semantic similarity catches wording variation. Retrieval hit rate checks grounding. Forbidden claim catches hallucination bait.

### Why store traces separately?

Trace payloads are larger than run item rows. Keeping traces in a side table makes run lists fast while still allowing detailed debugging when needed.

### Why does the candidate fail so badly in the demo?

The demo candidate intentionally injects forbidden synthetic claims. That makes the regression obvious and proves the gate can block a known-bad change.

### What is still missing?

Measured multi-worker Celery throughput, real repeated-run flakiness over adapter executions, deeper dashboard filters, final hand-labeled calibration findings, and demo video. The Docker/Celery smoke path is now verified locally, but production scale numbers are still not claimed.

## How To Study This Project

1. Read `PROJECT_BLUEPRINT.md` for the product idea.
2. Read `BUILD_PLAN.md` for the target standard.
3. Read `backend/app/models/entities.py` to understand the data model.
4. Read `backend/app/services/run_executor.py` to understand execution.
5. Read `backend/app/services/comparison.py` and `statistics.py` to understand gates.
6. Run backend tests.
7. Run the benchmark.
8. Open the frontend and click through Overview, Comparison, Traces, and Calibration.
9. Explain one failed case from trace to evaluator score.

If you can explain step 9 clearly, the project becomes interview-ready.
