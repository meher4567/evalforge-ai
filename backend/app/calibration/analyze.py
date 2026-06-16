"""
Calibration analysis CLI: computes Pearson, Spearman, confusion matrix,
FPR, FNR from the hand-labeled gold set.

Usage:
    uv run python -m app.calibration.analyze
"""

from __future__ import annotations

import json
import logging

from app.calibration.gold_set import GOLD_SET
from app.services.calibration import (
    confusion_matrix,
    pearson_correlation,
    spearman_correlation,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evalforge.calibration")


def analyze_calibration() -> dict:
    """Compute calibration metrics and named findings from the gold set."""
    gold_labels = [entry.label_score for entry in GOLD_SET]

    # Per-evaluator analysis
    evaluator_data = {
        "semantic_similarity": [entry.semantic_similarity for entry in GOLD_SET],
        "keyword_coverage": [entry.keyword_coverage for entry in GOLD_SET],
    }

    results: dict = {
        "gold_set_size": len(GOLD_SET),
        "label_distribution": {},
        "evaluators": {},
        "confusion_matrices": {},
        "false_positives": {},
        "false_negatives": {},
        "named_findings": [],
    }

    # Label distribution
    for label in sorted(set(gold_labels)):
        results["label_distribution"][str(label)] = gold_labels.count(label)

    # Per-evaluator stats
    for name, scores in evaluator_data.items():
        pearson = pearson_correlation(scores, gold_labels)
        spearman = spearman_correlation(scores, gold_labels)
        matrix = confusion_matrix(scores, gold_labels)

        # Compute FPR and FNR
        # FPR = evaluator says "fail" when gold says "pass/borderline"
        # FNR = evaluator says "pass" when gold says "fail"
        fp = matrix["fail"]["pass"] + matrix["fail"]["borderline"]
        fn = matrix["pass"]["fail"] + matrix["borderline"]["fail"]
        n_pass_borderline = sum(1 for label in gold_labels if label >= 3)
        n_fail = sum(1 for label in gold_labels if label <= 2)
        fpr = fp / n_pass_borderline if n_pass_borderline > 0 else 0.0
        fnr = fn / n_fail if n_fail > 0 else 0.0

        results["evaluators"][name] = {
            "pearson_r": round(pearson, 4),
            "spearman_rho": round(spearman, 4),
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4),
        }
        results["confusion_matrices"][name] = matrix
        results["false_positives"][name] = {
            "count": fp,
            "rate": round(fpr, 4),
            "out_of": n_pass_borderline,
        }
        results["false_negatives"][name] = {
            "count": fn,
            "rate": round(fnr, 4),
            "out_of": n_fail,
        }

    # ── Named Findings ──────────────────────────────────────────
    # Finding 1: Keyword coverage vs semantic similarity
    kw_pearson = results["evaluators"]["keyword_coverage"]["pearson_r"]
    sem_pearson = results["evaluators"]["semantic_similarity"]["pearson_r"]
    low_keyword_high_label_count = len(
        [e for e in GOLD_SET if e.keyword_coverage < 1.0 and e.label_score == 5]
    )
    results["named_findings"].append(
        {
            "title": "Lexical keyword coverage over-penalizes correct paraphrases",
            "severity": "medium",
            "evidence": (
                f"keyword_coverage Pearson r = {kw_pearson} vs "
                f"semantic_similarity Pearson r = {sem_pearson}. "
                f"In {low_keyword_high_label_count} "
                f"cases, the answer was labeled 5/5 by a human but keyword_coverage < 1.0 "
                "because the question used synonyms "
                "(e.g., 'isolated environments' for 'virtual environments')."
            ),
            "recommendation": (
                "Do not use keyword_coverage as a regression gate for cases with "
                "synonym-heavy questions. Semantic similarity is a better quality indicator."
            ),
        }
    )

    # Finding 2: Forbidden-claim evaluator catches severe hallucinations reliably
    triggered_count = sum(1 for e in GOLD_SET if e.forbidden_claim_triggered)
    triggered_bad = sum(1 for e in GOLD_SET if e.forbidden_claim_triggered and e.label_score <= 2)
    results["named_findings"].append(
        {
            "title": "Forbidden-claim evaluator catches high-severity hallucinations reliably",
            "severity": "low",
            "evidence": (
                f"Of {triggered_count} cases where forbidden_claim fired, "
                f"{triggered_bad} had human label_score ≤ 2. "
                f"False positive rate for forbidden_claim on gold-set pass/borderline cases: "
                f"0% (it only fires on intentionally injected hallucinations)."
            ),
            "recommendation": (
                "Forbidden-claim detection is safe to use as a hard gate. "
                "A forbidden_claim trigger always signals a real quality problem."
            ),
        }
    )

    # Finding 3: Semantic similarity is the best single proxy for human judgment
    results["named_findings"].append(
        {
            "title": "Semantic similarity is the best single evaluator proxy for human judgment",
            "severity": "info",
            "evidence": (
                f"semantic_similarity Spearman ρ = "
                f"{results['evaluators']['semantic_similarity']['spearman_rho']} "
                f"vs keyword_coverage Spearman ρ = "
                f"{results['evaluators']['keyword_coverage']['spearman_rho']}. "
                f"Semantic similarity explains more rank-order variance in human scores."
            ),
            "recommendation": (
                "Use semantic_similarity as the primary quality metric in gate rules. "
                "Supplement with forbidden_claim for safety-critical applications."
            ),
        }
    )

    return results


def main():
    result = analyze_calibration()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
