"""
Calibration analysis CLI: computes Pearson, Spearman, confusion matrix,
FPR and FNR from the author-scored synthetic calibration fixture.

Usage:
    uv run python -m app.calibration.analyze
"""

from __future__ import annotations

import json
import logging

from app.calibration.gold_set import SYNTHETIC_CALIBRATION_FIXTURE
from app.services.calibration import (
    confusion_matrix,
    pearson_correlation,
    spearman_correlation,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evalforge.calibration")


def analyze_calibration() -> dict:
    """Compute descriptive metrics for the synthetic fixture."""
    entries = SYNTHETIC_CALIBRATION_FIXTURE
    gold_labels = [entry.label_score for entry in entries]

    # Per-evaluator analysis
    evaluator_data = {
        "token_f1_overlap": [entry.token_f1_overlap for entry in entries],
        "keyword_coverage": [entry.keyword_coverage for entry in entries],
    }

    results: dict = {
        "study_type": "author_scored_synthetic_fixture",
        "independent_labelers": 0,
        "production_validated": False,
        "limitations": [
            "Cases are constructed from the deterministic demo dataset.",
            "Scores were assigned by the project author, without blinded independent review.",
            "Evaluator values are committed fixture data rather than a production run export.",
        ],
        "gold_set_size": len(entries),
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
    sem_pearson = results["evaluators"]["token_f1_overlap"]["pearson_r"]
    low_keyword_high_label_count = len(
        [e for e in entries if e.keyword_coverage < 1.0 and e.label_score == 5]
    )
    results["named_findings"].append(
        {
            "title": "Lexical keyword coverage over-penalizes correct paraphrases",
            "severity": "medium",
            "evidence": (
                f"keyword_coverage Pearson r = {kw_pearson} vs "
                f"token_f1_overlap Pearson r = {sem_pearson}. "
                f"In {low_keyword_high_label_count} "
                f"fixture cases received an author score of 5/5 but keyword_coverage < 1.0 "
                "because the question used synonyms "
                "(e.g., 'isolated environments' for 'virtual environments'). "
                "This is a hypothesis to validate with independent labels."
            ),
            "recommendation": (
                "Do not use keyword_coverage as a regression gate for cases with "
                "synonym-heavy questions without an independently labeled validation set."
            ),
        }
    )

    # Finding 2: Forbidden-claim evaluator detects injected phrases in this fixture.
    triggered_count = sum(1 for e in entries if e.forbidden_claim_triggered)
    triggered_bad = sum(1 for e in entries if e.forbidden_claim_triggered and e.label_score <= 2)
    results["named_findings"].append(
        {
            "title": "Forbidden-claim evaluator detects the injected fixture phrases",
            "severity": "low",
            "evidence": (
                f"Of {triggered_count} cases where forbidden_claim fired, "
                f"{triggered_bad} received author label_score ≤ 2. "
                "The phrases and expected detections were constructed together, so this does "
                "not measure performance on unseen hallucinations."
            ),
            "recommendation": (
                "Use exact forbidden-claim matching as one safety signal, then validate its "
                "coverage and false-positive rate on independently collected outputs."
            ),
        }
    )

    # Finding 3: Token overlap tracks the constructed author scores.
    results["named_findings"].append(
        {
            "title": "Token overlap tracks this fixture's author scores",
            "severity": "info",
            "evidence": (
                f"token_f1_overlap Spearman ρ = "
                f"{results['evaluators']['token_f1_overlap']['spearman_rho']} "
                f"vs keyword_coverage Spearman ρ = "
                f"{results['evaluators']['keyword_coverage']['spearman_rho']}. "
                "This relationship may be inflated by the fixture construction."
            ),
            "recommendation": (
                "Treat token overlap as a deterministic smoke-test metric. Calibrate semantic "
                "or judge-based gates on blinded, independently labeled real outputs."
            ),
        }
    )

    return results


def main():
    result = analyze_calibration()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
