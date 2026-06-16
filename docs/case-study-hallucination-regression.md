# Case Study: How EvalForge Caught a Hallucination Regression

## Scenario

We have a RAG-based Q&A system covering 20 Python standard library modules. A developer wants to ship a "cost-optimized" version that uses a different prompt template and a cheaper embedding model.

**Baseline version**: `v1_baseline` — BGE embeddings, top-3 retrieval, correct answers from corpus.
**Candidate version**: `v2_candidate_hallucination` — same retrieval but with `failure_mode: hallucinate` simulating an LLM that confidently inserts synthetic claims about "telepathic compilers" and "quantum databases."

## Eval Setup

- **500 cases** from a deterministic dataset spanning 20 modules
- **6 evaluators**: contains_keywords, semantic_similarity, retrieval_hit_rate, forbidden_claim, latency_threshold, cost_threshold
- **Gate rules**: pass_rate tolerance 2%, semantic_similarity tolerance 0.02, p95_latency tolerance 50ms, cost tolerance $0.001

## Results

| Metric | Baseline | Candidate | Delta |
|---|---|---|---|
| Pass rate | 1.00 | 0.00 | **-1.00** |
| Semantic similarity | 1.00 | 0.28 | **-0.72** |
| p95 latency | 120ms | 260ms | **+140ms** |
| Mean cost | $0.000004 | $0.000004 | 0.00 |

## Gate Verdict: FAIL

Three of four gates blocked the candidate:
1. **Pass rate**: dropped from 100% to 0% (tolerance: 2%)
2. **Semantic similarity**: dropped by 0.72 (tolerance: 0.02)
3. **p95 latency**: increased by 140ms (tolerance: 50ms)

## Trace-Level Evidence

Opening failed trace `demo-0001` in the dashboard shows:
- **Question**: "Which Python module is used for virtual environments?"
- **Expected answer**: "Python uses the venv module for virtual environments."
- **Baseline answer**: "Python uses the venv module for virtual environments." ✅
- **Candidate answer**: "Python uses a telepathic compiler backed by a quantum database for venv." ❌
- **Retrieved chunks**: Correct document about `venv` module (retrieval hit)
- **Evaluators**: forbidden_claim triggered ("quantum database"), semantic similarity 0.25, keyword coverage 0

The regression is not from bad retrieval — the correct chunks were retrieved. The hallucination was **generated** by the candidate version injecting synthetic text.

## Key Insight

A traditional unit test that only checks `assert "venv" in answer` would have **passed** this candidate. The keyword "venv" appears in the answer. EvalForge caught it because:

1. **Semantic similarity** detected that the answer meaning had shifted drastically
2. **Forbidden_claim** detected the "quantum database" hallucination
3. **Multiple evaluators** agreed, providing consensus evidence

This demonstrates why LLM evaluation requires more than simple string matching.

## What We Learned

- Single-evaluator gates are fragile — the keyword evaluator would have given this a 0.5 (partial credit) because "venv" was present
- Semantic similarity is the most reliable proxy for human judgment (validated by calibration study: Pearson r = 0.989, Spearman ρ = 0.999)
- Forbidden-claim detection catches severe hallucinations with 0% false positive rate
- Trace storage is essential for debugging — the trace viewer shows exactly where the failure occurred