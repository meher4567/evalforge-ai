# EvalForge Calibration Findings

## Status

This document is a calibration-ready findings template plus preliminary synthetic evidence from the deterministic demo benchmark. It is not yet the final hand-labeled calibration study. The final A-grade version requires the project owner to label the gold set manually using `docs/labeling_rubric.md`.

## Methodology For Final Study

- Select 50 RAG eval cases stratified across tags:
  - 10 easy
  - 10 hallucination risk
  - 10 retrieval required
  - 10 reasoning required
  - 10 adversarial or edge cases
- Run each selected case across the shipped app versions.
- Store three signals per output:
  - automated evaluator score,
  - optional LLM-judge score,
  - human label from the 1-5 rubric.
- Relabel 10 cases after 24 hours and report self-agreement.
- Split labels into 30 fit cases and 20 held-out validation cases if evaluator weighting is tuned.

## Preliminary Synthetic Finding

**Named finding:** Forbidden-claim checks catch hallucination-style regressions that token similarity alone only partially explains.

In the deterministic 500-case benchmark, the bad candidate injects the unsupported phrase "quantum database" into every answer. The gate fails the candidate on pass rate, semantic similarity, and p95 latency. The forbidden-claim evaluator is the clearest failure explanation at case level because it directly identifies the unsupported claim rather than only reporting a lower similarity score.

## Headline Benchmark Numbers

See `benchmarks/results/2026-05-31/demo_results.json`.

Current deterministic benchmark:

- 500 eval cases
- 1000 total case executions
- baseline pass rate: 1.0
- bad candidate pass rate: 0.0
- gate verdict: fail

## Limitations

- The current finding is synthetic, not hand-labeled.
- The current semantic evaluator is token-overlap based, not a sentence-transformer model.
- The final project owner must complete the human gold-set labels before using this as a resume calibration claim.
- Single-labeler calibration is weaker than multi-labeler calibration; self-agreement must be reported honestly.

## Final Study Checklist

- [ ] Choose 50 gold-set cases.
- [ ] Run all target versions.
- [ ] Label outputs using `docs/labeling_rubric.md`.
- [ ] Relabel 10 cases after 24 hours.
- [ ] Compute Pearson and Spearman correlations.
- [ ] Build confusion matrices.
- [ ] Write one final named finding from real labels.
- [ ] Replace this preliminary synthetic finding with the human-labeled result.
