# Demo Walkthrough

## Goal

This demo should make the interviewer understand EvalForge in under two minutes.

## Before Demo

Run checks:

```powershell
uv run --directory backend pytest
npm test --prefix frontend
npm run build --prefix frontend
```

Start frontend:

```powershell
npm run dev --prefix frontend
```

Open:

```text
http://127.0.0.1:5173
```

## 90-Second Script

### 0-15 seconds

"EvalForge is an evaluation and regression testing platform for RAG apps. Instead of manually testing a few prompts, it runs a suite of cases against a baseline and a candidate version."

Show:

- Overview page
- 500 cases
- candidate failed

### 15-35 seconds

"The dashboard shows the regression across pass rate, semantic similarity, p95 latency, and cost. The candidate fails because quality drops and latency increases beyond the gate tolerance."

Show:

- metric cards
- gate verdict
- comparison bars

### 35-60 seconds

"The important part is trace evidence. I can inspect a failed case, see the question, candidate answer, ground truth, retrieved context, and evaluator scores."

Show:

- trace inspector
- retrieved context
- failed answer

### 60-80 seconds

"The backend stores each run item, trace, and evaluator result separately. The comparison service computes bootstrap confidence intervals before making the gate decision."

Show:

- Comparison page
- Failure table filter

### 80-90 seconds

"I also added flaky-eval detection because LLM evals can be noisy. Repeated cases with high score variance should not drive hard deployment gates."

Show:

- Mention `benchmarks/results/2026-05-31/flaky_eval_results.json`

## Strong Closing Line

"The project is not a chatbot. It is infrastructure for safely changing AI systems."

## Questions To Invite

- "I can explain how the run executor persists traces."
- "I can explain why bootstrap CIs are used."
- "I can explain why calibration is still marked pending."
- "I can walk through one failed case from database row to dashboard."

## What Not To Say

Do not say:

- "This is production-ready."
- "This uses real distributed workers."
- "The calibration study is complete."
- "This proves model accuracy."

Say:

- "This is a strong local-first evaluation platform prototype."
- "The next production step is Celery workers and real deployment validation."
- "The calibration methodology is ready, but the hand-labeling study is pending."
