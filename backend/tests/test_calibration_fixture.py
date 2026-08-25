from app.calibration.analyze import analyze_calibration


def test_calibration_output_is_explicitly_non_production():
    result = analyze_calibration()

    assert result["study_type"] == "author_scored_synthetic_fixture"
    assert result["independent_labelers"] == 0
    assert result["production_validated"] is False
    assert result["limitations"]
    assert "token_f1_overlap" in result["evaluators"]
