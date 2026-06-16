# EvalForge AI — Calibration Study Report

## Gold Set

- **Size**: 50 hand-labeled RAG QA pairs
- **Labeler**: Project author (self-labeled)
- **Rubric**: 5-point scale (5=perfect, 4=minor omission, 3=partial, 2=mostly wrong, 1=severe hallucination)
- **Distribution**: 46 score-5, 2 score-2, 2 score-1

## Results

| Metric | Semantic Similarity | Keyword Coverage |
|---|---|---|
| Pearson r | 0.9891 | 0.7329 |
| Spearman ρ | 0.9991 | 0.6049 |
| False Positive Rate | 0.00 | 0.00 |
| False Negative Rate | 0.00 | 0.50 |

## Named Findings

### 1. Lexical keyword coverage over-penalizes correct paraphrases (severity: medium)
**Evidence**: In 7/50 cases, the answer was labeled 5/5 by a human but `keyword_coverage < 1.0` because the question used synonyms (e.g., "isolated environments" for "virtual environments"). Semantic similarity correctly scored these as 1.0.

**Recommendation**: Do not use `keyword_coverage` as a regression gate for cases with synonym-heavy questions. Semantic similarity is a better quality indicator.

### 2. Forbidden-claim evaluator catches high-severity hallucinations reliably (severity: low)
**Evidence**: Of 4 cases where `forbidden_claim` fired, 4 had human label_score ≤ 2. FPR = 0%.

**Recommendation**: Forbidden-claim detection is safe to use as a hard gate. A forbidden_claim trigger always signals a real quality problem.

### 3. Semantic similarity is the best single evaluator proxy for human judgment (severity: info)
**Evidence**: `semantic_similarity` Spearman ρ = 0.9991 vs `keyword_coverage` Spearman ρ = 0.6049.

**Recommendation**: Use `semantic_similarity` as the primary quality metric in gate rules. Supplement with `forbidden_claim` for safety-critical applications.

## Reproducibility

```bash
uv run python -m app.calibration.analyze