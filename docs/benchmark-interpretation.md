# Benchmark Interpretation Guide

This document explains how to read and reproduce the benchmark results committed in `benchmarks/results/`.

## Deterministic Demo Benchmark

**File:** `benchmarks/results/2026-05-31/demo_results.json`

**What it measures:** a fixed 500-case eval suite run against two demo versions using the real sync executor:

- `v1_baseline`: deterministic demo RAG adapter
- `v2_candidate_hallucination`: same adapter with injected hallucinations

| Metric | Baseline | Candidate | Interpretation |
|---|---:|---:|---|
| Pass rate | 1.00 | 0.00 | Candidate fails every case due to injected claims |
| Token-overlap similarity | 1.00 | 0.285 | Candidate shares few required tokens with expected answers |
| p95 latency | 120ms | 260ms | Candidate is intentionally slower |
| Mean cost | $0.000004 | $0.000004 | Demo cost is synthetic |

**Throughput:** about 4933 cases/minute in sync mode with the deterministic adapter.

**Gate verdict:** fail, blocked on pass rate, token-overlap similarity, and p95 latency.

## Caveats

The committed benchmark results are synthetic by design:

- no real LLM API calls
- no real RAG retrieval pipeline
- demo latency and cost constants are configured, not measured from an external provider
- the bad candidate's 0% pass rate is intentional

This is still useful for an evaluation infrastructure project because it proves the runner, trace storage, evaluator results, comparison metrics, confidence intervals, gates, and dashboard all work end to end.

## Real LLM Path

The repository includes `app.adapters.groq_chat`, which calls Groq's OpenAI-compatible API. Use the live smoke test when you intentionally want to spend free-tier quota:

```powershell
$env:EVALFORGE_RUN_LIVE_LLM_TESTS="1"
uv run --directory backend pytest tests/test_live_groq_integration.py -q
```

To turn this into a real benchmark, use a small suite, keep rate limits in mind, and record actual latency/cost rather than the deterministic demo constants.

## Worker Benchmark Path

`benchmarks/worker_throughput.py` is the worker throughput entry point. It requires Docker Compose because the worker path depends on Redis and a Celery worker:

```powershell
docker compose up --build
uv run --directory backend python ../benchmarks/worker_throughput.py
```

The Docker smoke workflow was verified locally on June 16, 2026 with:

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/healthz
docker compose exec -T backend uv run python -m app.cli.seed --mode celery --cases 50
```

That smoke completed a 50-case baseline run and a 50-case candidate run through Celery with zero errored cases, then computed the comparison. Local multi-worker throughput numbers are still pending.

## Reproduce

```powershell
uv sync --directory backend
uv run --directory backend python ../benchmarks/run_demo.py --cases 500
uv run --directory backend python ../benchmarks/flaky_eval.py
```

Do not compare the deterministic throughput number to production LLM throughput. Real provider calls and embedding evaluators will be much slower and should be measured separately.
