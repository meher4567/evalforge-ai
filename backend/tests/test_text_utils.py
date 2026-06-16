"""
Unit tests for the text utility module (tokenize, normalize_text, token_f1).
"""

import pytest

from app.evaluators.text import normalize_text, token_f1, tokenize


class TestTokenize:
    def test_simple_sentence(self):
        tokens = tokenize("Hello, world! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_numbers_and_underscores(self):
        tokens = tokenize("test_123 and 456")
        assert tokens == ["test", "123", "and", "456"]

    def test_empty_string(self):
        assert tokenize("") == []

    def test_only_punctuation(self):
        assert tokenize("!!!???") == []

    def test_cjk_characters_are_skipped(self):
        # Pattern is [a-z0-9]+ so CJK is dropped; only ASCII tokens survive
        assert tokenize("\u4f60\u597d world") == ["world"]

    def test_accents_lowered(self):
        assert tokenize("Café") == ["caf"]


class TestNormalizeText:
    def test_whitespace_normalization(self):
        assert normalize_text("Hello   world") == "hello world"

    def test_case_insensitive(self):
        assert normalize_text("HELLO") == "hello"

    def test_punctuation_removal(self):
        assert normalize_text("Hello, world!") == "hello world"

    def test_empty_string(self):
        assert normalize_text("") == ""


class TestTokenF1:
    def test_identical_strings(self):
        assert token_f1("hello world", "hello world") == 1.0

    def test_complete_mismatch(self):
        assert token_f1("abc", "xyz") == 0.0

    def test_partial_overlap(self):
        score = token_f1("hello world", "hello there")
        # left: hello, world (2) ; right: hello, there (2)
        # overlap: hello (1)
        # precision = 1/2, recall = 1/2, f1 = 0.5
        assert score == 0.5

    def test_subset(self):
        score = token_f1("hello world", "hello")
        # left: hello, world (2) ; right: hello (1)
        # overlap: hello (1)
        # precision = 1/2, recall = 1/1, f1 = 2*(0.5*1)/(1.5) = 0.666...
        assert score == pytest.approx(2.0 / 3.0)

    def test_one_empty_returns_zero(self):
        assert token_f1("hello", "") == 0.0
        assert token_f1("", "hello") == 0.0

    def test_both_empty_returns_zero(self):
        assert token_f1("", "") == 0.0
