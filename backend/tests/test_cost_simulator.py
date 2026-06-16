"""
Unit tests for the cost simulator.

Covers: count_tokens, estimate_cost, model rate lookup,
and edge cases (empty strings, unknown models, missing config).
"""

from app.services.cost_simulator import _get_model_rates, count_tokens, estimate_cost


class TestCountTokens:
    def test_non_empty_text_returns_positive_count(self):
        tokens = count_tokens("Hello, world!", "gpt-3.5-turbo")
        assert tokens > 0

    def test_empty_string_returns_zero(self):
        assert count_tokens("", "gpt-3.5-turbo") == 0

    def test_long_text_more_tokens(self):
        short = count_tokens("hi", "gpt-3.5-turbo")
        long_text = "The quick brown fox jumps over the lazy dog many times."
        long = count_tokens(long_text, "gpt-3.5-turbo")
        assert long > short

    def test_unknown_model_uses_fallback(self):
        """Unknown model should use char/4 fallback without error."""
        tokens = count_tokens("hello world", "nonexistent-model-v9")
        assert tokens > 0

    def test_gpt4_model_uses_cl100k(self):
        tokens = count_tokens("hello", "gpt-4o")
        assert tokens > 0


class TestEstimateCost:
    def test_known_model_returns_positive_cost(self):
        cost, in_tokens, out_tokens = estimate_cost(
            "What is Python?", "Python is a programming language.", "gpt-3.5-turbo"
        )
        assert cost > 0
        assert in_tokens > 0
        assert out_tokens > 0

    def test_empty_response_zero_tokens(self):
        cost, in_tokens, out_tokens = estimate_cost("prompt", "", "gpt-3.5-turbo")
        assert out_tokens == 0
        assert cost >= 0

    def test_unknown_model_uses_default_rates(self):
        cost, in_tokens, out_tokens = estimate_cost("hello", "world", "unknown-model-xyz")
        assert cost >= 0
        assert in_tokens > 0
        assert out_tokens > 0

    def test_cost_is_proportional_to_tokens(self):
        """More tokens => higher cost."""
        short_cost, _, _ = estimate_cost("hi", "ok", "gpt-3.5-turbo")
        long_cost, _, _ = estimate_cost("a" * 500, "b" * 500, "gpt-3.5-turbo")
        assert long_cost > short_cost

    def test_cost_is_rounded_to_8_decimal_places(self):
        cost, _, _ = estimate_cost("test", "test", "gpt-3.5-turbo")
        cost_str = f"{cost:.8f}"
        reconstructed = float(cost_str)
        assert reconstructed == cost


class TestGetModelRates:
    def test_known_model_returns_numeric_rates(self):
        in_rate, out_rate = _get_model_rates("gpt-4o")
        assert isinstance(in_rate, float)
        assert isinstance(out_rate, float)
        assert in_rate > 0
        assert out_rate > 0

    def test_unknown_model_falls_back_to_default(self):
        in_rate, out_rate = _get_model_rates("completely-fake-model-999")
        assert in_rate > 0
        assert out_rate > 0

    def test_output_rate_typically_higher_than_input(self):
        """Most model pricing has output > input rate."""
        in_rate, out_rate = _get_model_rates("gpt-3.5-turbo")
        assert out_rate >= in_rate
