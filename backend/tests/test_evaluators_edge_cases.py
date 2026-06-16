"""
Edge-case and boundary tests for individual evaluator functions.

Tests exact_match, contains_keywords, forbidden_claim, latency_threshold,
cost_threshold evaluators with corner-case inputs.
"""

from app.adapters.base import AdapterOutput
from app.evaluators.basic import (
    contains_keywords,
    cost_threshold,
    embedding_similarity,
    exact_match,
    forbidden_claim,
    latency_threshold,
    retrieval_hit_rate,
    semantic_similarity,
    skipped,
    token_f1_overlap,
)


def _make_output(answer="test", chunks=None, latency=100, cost=0.001):
    return AdapterOutput(
        answer=answer,
        retrieved_chunks=chunks or [],
        prompt_used="test_prompt",
        model_used="test_model",
        latency_ms=latency,
        estimated_cost_usd=cost,
        trace_steps=[],
    )


class TestExactMatch:
    def test_match(self):
        result = exact_match(
            {"expected_output": "hello world"},
            _make_output("hello world"),
            {},
        )
        assert result.score == 1.0
        assert result.passed is True

    def test_no_match(self):
        result = exact_match(
            {"expected_output": "hello"},
            _make_output("goodbye"),
            {},
        )
        assert result.score == 0.0
        assert result.passed is False

    def test_normalized_whitespace_match(self):
        result = exact_match(
            {"expected_output": "  hello   world  "},
            _make_output("hello world"),
            {},
        )
        assert result.score == 1.0
        assert result.passed is True

    def test_case_insensitive(self):
        result = exact_match(
            {"expected_output": "HELLO"},
            _make_output("hello"),
            {},
        )
        assert result.score == 1.0
        assert result.passed is True

    def test_missing_expected_output_skips(self):
        result = exact_match({}, _make_output("test"), {})
        assert result.skipped is True
        assert result.evaluator_name == "exact_match"

    def test_empty_strings_match(self):
        result = exact_match(
            {"expected_output": ""},
            _make_output(""),
            {},
        )
        assert result.score == 1.0


class TestContainsKeywords:
    def test_all_facts_present(self):
        result = contains_keywords(
            {"expected_facts": ["hello", "world"]},
            _make_output("hello world"),
            {"threshold": 1.0},
        )
        assert result.score == 1.0
        assert result.passed is True

    def test_partial_match(self):
        result = contains_keywords(
            {"expected_facts": ["hello", "world"]},
            _make_output("hello there"),
            {"threshold": 0.5},
        )
        assert result.score == 0.5
        assert result.passed is True

    def test_partial_match_below_threshold(self):
        result = contains_keywords(
            {"expected_facts": ["hello", "world", "python"]},
            _make_output("hello there"),
            {"threshold": 0.8},
        )
        assert result.score < 0.8
        assert result.passed is False

    def test_case_insensitive(self):
        result = contains_keywords(
            {"expected_facts": ["HELLO"]},
            _make_output("hello world"),
            {},
        )
        assert result.score == 1.0

    def test_missing_facts_skips(self):
        result = contains_keywords({}, _make_output("test"), {})
        assert result.skipped is True

    def test_empty_facts_skips(self):
        result = contains_keywords(
            {"expected_facts": []},
            _make_output("test"),
            {},
        )
        assert result.skipped is True

    def test_substring_not_whole_word(self):
        """contain should match substrings, not just whole words."""
        result = contains_keywords(
            {"expected_facts": ["hell"]},
            _make_output("hello world"),
            {},
        )
        assert result.score == 1.0

    def test_details_include_missed_facts(self):
        result = contains_keywords(
            {"expected_facts": ["hello", "absent"]},
            _make_output("hello world"),
            {},
        )
        assert "absent" in result.details["facts_missed"]


class TestForbiddenClaim:
    def test_no_forbidden_claims_found(self):
        result = forbidden_claim(
            {"forbidden_claims": ["quantum database"]},
            _make_output("normal answer"),
            {},
        )
        assert result.passed is True
        assert result.score == 1.0

    def test_forbidden_claim_found(self):
        result = forbidden_claim(
            {"forbidden_claims": ["quantum database"]},
            _make_output("uses quantum database for storage"),
            {},
        )
        assert result.passed is False
        assert result.score == 0.0

    def test_missing_claims_skips(self):
        result = forbidden_claim({}, _make_output("test"), {})
        assert result.skipped is True

    def test_empty_claims_skips(self):
        result = forbidden_claim(
            {"forbidden_claims": []},
            _make_output("test"),
            {},
        )
        assert result.skipped is True

    def test_case_insensitive_match(self):
        result = forbidden_claim(
            {"forbidden_claims": ["Quantum Database"]},
            _make_output("quantum database used"),
            {},
        )
        assert result.passed is False

    def test_multiple_claims_one_triggered(self):
        result = forbidden_claim(
            {"forbidden_claims": ["good claim", "bad claim"]},
            _make_output("this contains a bad claim"),
            {},
        )
        assert result.passed is False
        assert "bad claim" in result.details["triggered_claims"]


class TestLatencyThreshold:
    def test_under_threshold(self):
        result = latency_threshold({}, _make_output(latency=50), {"threshold_ms": 100})
        assert result.passed is True
        assert result.score == 1.0

    def test_over_threshold(self):
        result = latency_threshold({}, _make_output(latency=300), {"threshold_ms": 200})
        assert result.passed is False
        assert result.score < 1.0

    def test_decreasing_score_formula(self):
        """Score decreases linearly as latency exceeds threshold."""
        result = latency_threshold({}, _make_output(latency=400), {"threshold_ms": 200})
        # score = max(0, 1 - (400-200)/200) = max(0, 1 - 1) = 0
        assert result.score == 0.0

    def test_very_high_latency_floor_zero(self):
        result = latency_threshold({}, _make_output(latency=10000), {"threshold_ms": 200})
        assert result.score >= 0.0

    def test_default_threshold(self):
        result = latency_threshold({}, _make_output(latency=500), {})
        # Default threshold is 2000
        assert result.passed is True
        assert result.score == 1.0


class TestCostThreshold:
    def test_under_threshold(self):
        result = cost_threshold({}, _make_output(cost=0.001), {"threshold_usd": 0.01})
        assert result.passed is True
        assert result.score == 1.0

    def test_over_threshold(self):
        result = cost_threshold({}, _make_output(cost=0.05), {"threshold_usd": 0.01})
        assert result.passed is False
        assert result.score < 1.0

    def test_decreasing_formula(self):
        result = cost_threshold({}, _make_output(cost=0.02), {"threshold_usd": 0.01})
        # score = max(0, 1 - (0.02-0.01)/0.01) = 0
        assert result.score == 0.0

    def test_default_threshold(self):
        result = cost_threshold({}, _make_output(cost=0.005), {})
        assert result.passed is True


class TestRetrievalHitRate:
    def test_expected_doc_in_chunks(self):
        result = retrieval_hit_rate(
            {"expected_doc_id": "venv"},
            _make_output(chunks=[{"doc_id": "venv", "chunk_text": "text"}]),
            {},
        )
        assert result.passed is True
        assert result.score == 1.0

    def test_expected_doc_not_in_chunks(self):
        result = retrieval_hit_rate(
            {"expected_doc_id": "venv"},
            _make_output(chunks=[{"doc_id": "other", "chunk_text": "text"}]),
            {},
        )
        assert result.passed is False
        assert result.score == 0.0

    def test_missing_expected_id_skips(self):
        result = retrieval_hit_rate({}, _make_output(), {})
        assert result.skipped is True

    def test_empty_chunks_not_hit(self):
        result = retrieval_hit_rate(
            {"expected_doc_id": "venv"},
            _make_output(chunks=[]),
            {},
        )
        assert result.passed is False

    def test_uses_expected_chunk_id_alias(self):
        result = retrieval_hit_rate(
            {"expected_chunk_id": "venv"},
            _make_output(chunks=[{"doc_id": "venv"}]),
            {},
        )
        assert result.passed is True


class TestTokenF1Overlap:
    def test_scores_token_overlap_with_honest_name(self):
        result = token_f1_overlap(
            {"expected_output": "Python uses venv for virtual environments."},
            _make_output("Python uses the venv module for virtual environments."),
            {"threshold": 0.5},
        )

        assert result.evaluator_name == "token_f1_overlap"
        assert result.passed is True
        assert result.details["method"] == "token_f1"

    def test_legacy_semantic_similarity_is_marked_as_token_overlap_alias(self):
        result = semantic_similarity(
            {"expected_output": "Python uses venv."},
            _make_output("Python uses venv."),
            {},
        )

        assert result.evaluator_name == "semantic_similarity"
        assert result.details["method"] == "token_f1"
        assert result.details["alias_for"] == "token_f1_overlap"


class TestEmbeddingSimilarity:
    def test_scores_embedding_cosine_similarity(self, monkeypatch):
        vectors = {
            "expected answer": [1.0, 0.0],
            "candidate answer": [0.8, 0.6],
        }

        monkeypatch.setattr(
            "app.evaluators.basic.compute_embedding_sync",
            lambda value: vectors[value],
        )

        result = embedding_similarity(
            {"expected_output": "expected answer"},
            _make_output("candidate answer"),
            {"threshold": 0.75},
        )

        assert result.evaluator_name == "embedding_similarity"
        assert result.score == 0.8
        assert result.passed is True
        assert result.details["model"] == "all-MiniLM-L6-v2"
        assert result.details["method"] == "sentence_transformer_cosine"

    def test_missing_expected_output_skips(self):
        result = embedding_similarity({}, _make_output("candidate answer"), {})

        assert result.evaluator_name == "embedding_similarity"
        assert result.skipped is True


class TestSkippedHelper:
    def test_skipped_result_has_correct_shape(self):
        result = skipped("test_eval", "reason text")
        assert result.evaluator_name == "test_eval"
        assert result.skipped is True
        assert result.score is None
        assert result.passed is None
        assert result.details["reason"] == "reason text"
        assert result.errored is False
