# Learning Roadmap For Explaining EvalForge

This roadmap is for becoming able to explain the project honestly in interviews.

## Level 1: Product Story

You should be able to answer:

- What problem does EvalForge solve?
- Why are normal unit tests not enough for LLM apps?
- What is a baseline version?
- What is a candidate version?
- What is an eval suite?
- Why does the demo candidate fail?

Practice explanation:

> EvalForge tests whether a new RAG version is safe to ship by running the same cases against a baseline and candidate, scoring outputs, storing traces, and applying regression gates.

## Level 2: Backend Flow

Read these files:

- `backend/app/api/runs.py`
- `backend/app/services/run_executor.py`
- `backend/app/evaluators/engine.py`
- `backend/app/services/comparison.py`

You should be able to explain:

- request enters FastAPI
- run row is created
- cases are loaded from a suite
- adapter is called for each case
- evaluator results are stored
- trace is stored
- run counters are updated

## Level 3: Data Model

Read:

- `backend/app/models/entities.py`
- `docs/architecture.md`

You should be able to draw:

```text
App -> AppVersion -> EvalRun -> EvalRunItem -> Trace/EvalResult
App -> EvalSuite -> EvalCase
Comparison -> RegressionReport
```

Key idea:

> A comparison is between two completed runs, not between two mutable prompts.

## Level 4: Evaluator Logic

Read:

- `backend/app/evaluators/basic.py`
- `backend/app/evaluators/text.py`
- `docs/eval-metrics.md`

Explain:

- exact match
- keyword coverage
- semantic similarity
- retrieval hit rate
- forbidden claim detection
- latency and cost thresholds

## Level 5: Statistics

Read:

- `backend/app/services/statistics.py`
- `backend/app/services/comparison.py`

Understand:

- average
- percentile
- bootstrap confidence interval
- delta confidence interval
- gate tolerance

Interview-safe explanation:

> A small pass-rate delta might be sampling noise. Bootstrap resampling gives a confidence interval so the gate does not overreact to tiny unstable differences.

## Level 6: Frontend

Read:

- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/components/TraceInspector.tsx`
- `frontend/src/components/ComparisonBars.tsx`

Explain:

- app shell state
- active view
- selected run
- selected trace
- API fallback order
- trace inspector UI

## Level 7: Advanced Rigor

Read:

- `backend/app/services/flakiness.py`
- `docs/phase-6-flaky-eval-design.md`
- `docs/calibration_findings.md`

Explain:

- why evals can be flaky
- why high-variance cases should not hard-fail deployments
- why calibration is not complete yet
- how a hand-labeled gold set would validate evaluators

## Final Practice Drill

Pick one failed trace and explain:

1. What was the question?
2. What did the baseline answer?
3. What did the candidate answer?
4. Which evaluator failed?
5. What retrieved context was available?
6. Why did the gate fail?
7. What would you change in the candidate version?

If you can answer those seven questions cleanly, you can defend the project.
