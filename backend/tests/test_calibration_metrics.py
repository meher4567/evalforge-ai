from app.services.calibration import confusion_matrix, pearson_correlation, spearman_correlation


def test_calibration_correlations_detect_strong_agreement():
    labels = [5, 4, 3, 2, 1]
    evaluator_scores = [1.0, 0.8, 0.55, 0.3, 0.0]

    assert pearson_correlation(evaluator_scores, labels) > 0.98
    assert spearman_correlation(evaluator_scores, labels) == 1.0


def test_confusion_matrix_bins_scores_against_gold_labels():
    matrix = confusion_matrix(
        evaluator_scores=[0.9, 0.6, 0.2],
        gold_labels=[5, 3, 1],
    )

    assert matrix == {
        "pass": {"pass": 1, "borderline": 0, "fail": 0},
        "borderline": {"pass": 0, "borderline": 1, "fail": 0},
        "fail": {"pass": 0, "borderline": 0, "fail": 1},
    }
