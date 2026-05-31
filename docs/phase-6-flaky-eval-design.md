# Phase 6 Flaky-Eval Detection

## Goal

LLM and RAG evals can be nondeterministic. A case can pass once, fail once, and pass again without any code change. If a regression gate treats that case as stable, the platform can block a candidate for noise instead of a real regression.

This phase adds a deterministic flaky-eval classifier that can be used after repeated runs.

## Protocol

For each selected case:

1. Run the same case against the same app version multiple times.
2. Collect the primary evaluator score for each run.
3. Compute population standard deviation.
4. Classify the case:

| Classification | Rule |
|---|---|
| stable | score standard deviation `< 0.05` |
| flaky | `0.05 <= stddev < 0.20` |
| inconclusive | stddev `>= 0.20` |

Flaky and inconclusive cases should be excluded from hard gate decisions or reviewed separately.

## Implementation

Core service:

- `backend/app/services/flakiness.py`

Public functions:

- `classify_flaky_cases(observations)`
- `summarize_flakiness(classifications)`

Tests:

- `backend/tests/test_flakiness.py`

Benchmark:

- `benchmarks/flaky_eval.py`

Committed result:

- `benchmarks/results/2026-05-31/flaky_eval_results.json`

## Current Benchmark Result

The deterministic synthetic flaky benchmark produced:

- total cases: 50
- repeated scores per case: 5
- stable: 25
- flaky: 15
- inconclusive: 10
- excluded from gate: 25

This benchmark is synthetic. It proves the classifier and reporting path work, not that the real RAG adapter has this exact flaky rate.

## Interview Explanation

The important idea is that eval quality gates should not treat nondeterministic cases like stable unit tests. If a case has high variance across repeated runs, a fail on that case is weak evidence. EvalForge classifies repeated-score variance and reports which cases should be excluded from hard gates.

This is a production-thinking feature because it prevents noisy evals from creating false alarms.

## Next Step

The current benchmark uses synthetic repeated scores. The next version should run a real subset of tagged eval cases `N=5` times through the adapter and feed the observed scores into this same service.
