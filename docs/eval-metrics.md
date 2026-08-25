# Evaluation Metrics

## Why Metrics Need Multiple Views

LLM and RAG apps fail in different ways. One score cannot capture everything:

- exact answer wrong
- answer misses required facts
- answer sounds similar but is hallucinated
- retriever found the wrong chunk
- model is correct but too slow
- candidate is cheaper but lower quality

EvalForge uses multiple evaluators and then gate rules decide whether the candidate is acceptable.

## Implemented Evaluators

| Evaluator | What it checks | Output |
|---|---|---|
| `exact_match` | answer equals expected output | score `0` or `1` |
| `contains_keywords` | expected facts appear in answer | fraction of facts hit |
| `token_f1_overlap` | lexical token overlap with expected answer | score from `0` to `1` |
| `semantic_similarity` | backward-compatible alias for `token_f1_overlap` | score from `0` to `1` |
| `embedding_similarity` | sentence-transformer cosine similarity | score from `0` to `1` |
| `faithfulness` | batched NLI entailment of answer sentences against retrieved context | score from `0` to `1` |
| `retrieval_hit_rate` | expected document/chunk was retrieved | score `0` or `1` |
| `forbidden_claim` | hallucination bait appears in answer | pass/fail |
| `latency_threshold` | case latency under threshold | pass/fail |
| `cost_threshold` | estimated cost under threshold | pass/fail |

## Pass Rate

For each case:

```text
case_pass = 1 if all applicable evaluators pass else 0
```

Run pass rate:

```text
pass_rate = sum(case_pass) / case_count
```

Skipped evaluators are excluded from that evaluator's denominator. Errored evaluators are recorded and count as case failures so infrastructure or evaluator faults cannot silently improve pass rate.

## Similarity Evaluators

EvalForge now separates lexical overlap from real semantic similarity.

`token_f1_overlap` is deterministic and lightweight. It uses token-level F1 and is appropriate for fast CI benchmarks.

`semantic_similarity` remains available as a backward-compatible alias for old evaluator configs. It is intentionally marked in result details as an alias for `token_f1_overlap`, so the project does not pretend lexical overlap is an embedding model.

`embedding_similarity` uses `sentence-transformers` with `all-MiniLM-L6-v2` and cosine similarity. It is a real local embedding evaluator, but it is slower than token F1 and should be used for smaller suites or calibration work.

`faithfulness` uses an optional NLI model to score up to five answer sentences against retrieved context in one inference batch. Both ML evaluators require the `ml` dependency group; `GET /api/evaluators` reports whether their modules are available before a config is accepted.

Why keep the lexical path:

- no paid API dependency
- fast benchmark
- easy to explain and audit
- stable results for CI

Limitation:

- lexical/token similarity can miss paraphrases
- fluent hallucinations can score higher than they deserve

This limitation is exactly why `embedding_similarity`, `forbidden_claim`, and the calibration study exist.

## Retrieval Hit Rate

Retrieval hit rate checks whether the expected document id appears in the retrieved chunks.

```text
retrieval_hit = expected_doc_id in retrieved_doc_ids
```

This is strong for RAG because an answer can only be grounded if the right evidence was retrieved.

## Forbidden Claim Detection

The demo candidate injects forbidden synthetic claims such as:

- `quantum database`
- `telepathic compiler`

The evaluator fails when these claims appear in the answer.

This gives a clean synthetic regression benchmark: the bad candidate should fail.

## Latency And Cost

Latency is recorded per run item. Cost is estimated by the adapter for the deterministic demo.

The comparison service reports:

- p95 latency
- mean cost

Cost is tiny in the deterministic demo because no paid model API is called.

## Bootstrap Confidence Intervals

Point estimates alone can be misleading. EvalForge computes bootstrap confidence intervals for:

- pass rate
- token-overlap / semantic-alias similarity
- p95 latency
- mean cost

The idea:

1. Resample cases with replacement.
2. Recompute the metric.
3. Repeat many times.
4. Use the distribution to estimate a confidence interval.

This helps separate real regressions from noise.

## Gate Logic

Each metric has:

- direction: higher is better or lower is better
- tolerance: acceptable regression amount
- verdict: pass, warn, or fail

A candidate fails when the regression is beyond tolerance and the confidence interval supports that decision.

Current default gates:

| Metric | Direction | Tolerance |
|---|---|---|
| pass rate | higher is better | `0.02` |
| token-overlap similarity | higher is better | `0.02` |
| p95 latency | lower is better | `50ms` |
| mean cost | lower is better | current demo uses a loose cost tolerance |

## Flaky-Eval Detection

Repeated scores are classified by standard deviation:

| Classification | Rule |
|---|---|
| stable | stddev `< 0.05` |
| flaky | `0.05 <= stddev < 0.20` |
| inconclusive | stddev `>= 0.20` |

Flaky and inconclusive cases should not drive hard gate failures.

## Calibration Study

The calibration study is the next major rigor step:

1. Select 50 cases across tags.
2. Label outputs using `docs/labeling_rubric.md`.
3. Compare automated evaluator scores against human labels.
4. Report Pearson, Spearman, confusion matrix, and one named finding.

Until that is complete, calibration numbers should be treated as preliminary.
