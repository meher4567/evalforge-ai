# EvalForge AI — Synthetic Calibration Fixture Report

## Study status

This repository currently contains a 50-case, author-scored synthetic fixture. It exercises the calibration code and demonstrates the intended reporting format. It is **not** an independently labeled gold set and must not be treated as evidence that an evaluator is production-calibrated.

- Source: deterministic demo questions and deliberately injected failures
- Scoring: one project author, using the 5-point rubric
- Independent labelers: 0
- Blinding: none
- Inter-rater agreement: not measured
- External or production outputs: none

## Descriptive fixture results

| Metric | Token F1 overlap | Keyword coverage |
|---|---:|---:|
| Pearson r | 0.9891 | 0.7329 |
| Spearman ρ | 0.9991 | 0.6049 |
| False-positive rate | 0.00 | 0.00 |
| False-negative rate | 0.00 | 0.50 |

These values describe only the constructed fixture. Because cases, expected outcomes, failure phrases, and author scores were designed together, the correlations are likely optimistic.

## What the fixture suggests

1. Exact keyword coverage can penalize correct paraphrases. Validate this hypothesis on independently labeled outputs before changing a production gate.
2. Forbidden-claim matching detects the exact injected phrases. It does not establish recall on novel hallucinations.
3. Token F1 overlap tracks the author scores in this simple lexical dataset. It is a reproducible smoke-test metric, not a substitute for semantic or human evaluation.

## Required path to a real calibration result

1. Sample real outputs across difficulty, domain, model, and failure categories.
2. Freeze the rubric and evaluator thresholds before labeling.
3. Use at least two independent, blinded labelers and adjudicate disagreements.
4. Report label distribution, weighted Cohen’s kappa, confidence intervals, FPR/FNR, and per-slice results.
5. Hold out a test split and avoid tuning thresholds on it.
6. Publish anonymized input/output hashes and a versioned study manifest where data policy permits.

## Reproduction

```bash
uv run --directory backend python -m app.calibration.analyze
```
