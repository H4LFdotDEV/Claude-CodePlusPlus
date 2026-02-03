"""Tests for cost tracker."""

import time
import pytest
from shared.cost_tracker import (
    CostTracker,
    BudgetExceededError,
    MODEL_PRICING,
)


def test_basic_cost_tracking():
    """Test basic cost tracking for a single model."""
    tracker = CostTracker()

    # Track a Haiku call: 1000 input, 500 output tokens
    cost = tracker.track("claude-haiku-4-5", 1000, 500)

    # Expected: 1000 * 0.25/1M + 500 * 1.25/1M = 0.00025 + 0.000625 = 0.000875
    expected_cost = 0.000875
    assert abs(cost - expected_cost) < 1e-9
    assert abs(tracker.total_cost - expected_cost) < 1e-9


def test_token_counting():
    """Test token counting across multiple calls."""
    tracker = CostTracker()

    # Make multiple calls
    tracker.track("claude-sonnet-4-5", 1000, 500)
    tracker.track("claude-sonnet-4-5", 2000, 1000)
    tracker.track("claude-haiku-4-5", 500, 250)

    # Check total tokens
    totals = tracker.total_tokens
    assert totals["input"] == 3500
    assert totals["output"] == 1750

    # Check per-model tokens
    assert tracker._token_counts["claude-sonnet-4-5"]["input"] == 3000
    assert tracker._token_counts["claude-sonnet-4-5"]["output"] == 1500
    assert tracker._token_counts["claude-haiku-4-5"]["input"] == 500
    assert tracker._token_counts["claude-haiku-4-5"]["output"] == 250


def test_call_counting():
    """Test call counting."""
    tracker = CostTracker()

    # Make multiple calls
    tracker.track("claude-sonnet-4-5", 1000, 500)
    tracker.track("claude-sonnet-4-5", 2000, 1000)
    tracker.track("claude-haiku-4-5", 500, 250)
    tracker.track("claude-haiku-4-5", 1000, 500)

    # Check total calls
    assert tracker.total_calls == 4

    # Check per-model calls
    assert tracker._call_counts["claude-sonnet-4-5"] == 2
    assert tracker._call_counts["claude-haiku-4-5"] == 2


def test_budget_limit_enforced():
    """Test that budget limit is enforced."""
    tracker = CostTracker(budget_limit=0.02)  # $0.02 limit

    # First call should succeed (under budget)
    tracker.track("claude-sonnet-4-5", 1000, 500)  # ~$0.0105

    # Second call should raise BudgetExceededError (would exceed budget)
    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.track("claude-sonnet-4-5", 1000, 500)  # Would bring total to ~$0.021

    assert "exceeds budget" in str(exc_info.value)
    assert "$0.02" in str(exc_info.value)


def test_budget_limit_not_enforced_when_disabled():
    """Test that budget limit can be disabled."""
    tracker = CostTracker(budget_limit=0.005)  # Very low budget

    # First call with raise_on_budget=False should succeed even though over budget
    cost = tracker.track("claude-sonnet-4-5", 1000, 500, raise_on_budget=False)
    assert cost > 0
    assert tracker.total_cost > 0.005  # Over budget but no exception

    # Second call with raise_on_budget=False should also succeed
    cost2 = tracker.track("claude-sonnet-4-5", 1000, 500, raise_on_budget=False)
    assert cost2 > 0
    assert tracker.total_cost > 0.01  # Way over budget but no exception


def test_budget_remaining():
    """Test budget remaining calculation."""
    tracker = CostTracker(budget_limit=0.02)

    # Initially, full budget available
    assert tracker.budget_remaining == 0.02
    assert tracker.budget_percent_used == 0.0

    # After first call
    tracker.track("claude-sonnet-4-5", 1000, 500)  # ~$0.0105
    assert tracker.budget_remaining is not None
    assert 0.009 < tracker.budget_remaining < 0.011
    assert 50 < tracker.budget_percent_used < 55

    # After second call (over budget)
    tracker.track("claude-sonnet-4-5", 1000, 500, raise_on_budget=False)
    assert tracker.budget_remaining == 0  # Can't go negative
    assert tracker.budget_percent_used == 100  # Capped at 100%


def test_no_budget_set():
    """Test behavior when no budget is set."""
    tracker = CostTracker()

    # Make expensive calls
    tracker.track("claude-opus-4-5", 100000, 50000)

    # No budget-related errors
    assert tracker.budget_remaining is None
    assert tracker.budget_percent_used is None


def test_stats_reporting():
    """Test comprehensive stats reporting."""
    tracker = CostTracker(budget_limit=1.0)

    # Make some calls
    tracker.track("claude-sonnet-4-5", 1000, 500)
    tracker.track("claude-haiku-4-5", 2000, 1000)

    # Allow time to pass for duration calculation
    time.sleep(0.1)

    stats = tracker.get_stats()

    # Check structure
    assert "session_total_usd" in stats
    assert "by_model" in stats
    assert "token_counts" in stats
    assert "total_tokens" in stats
    assert "call_counts" in stats
    assert "total_calls" in stats
    assert "budget_limit_usd" in stats
    assert "budget_remaining_usd" in stats
    assert "budget_percent_used" in stats
    assert "session_duration_seconds" in stats
    assert "cost_per_minute_usd" in stats

    # Check values
    assert stats["total_calls"] == 2
    assert stats["budget_limit_usd"] == 1.0
    assert stats["session_duration_seconds"] > 0
    assert "claude-sonnet-4-5" in stats["by_model"]
    assert "claude-haiku-4-5" in stats["by_model"]


def test_model_breakdown():
    """Test model breakdown reporting."""
    tracker = CostTracker()

    # Make calls to different models with different costs
    tracker.track("claude-opus-4-5", 10000, 5000)  # Most expensive
    tracker.track("claude-sonnet-4-5", 10000, 5000)  # Medium
    tracker.track("claude-haiku-4-5", 10000, 5000)  # Cheapest

    breakdown = tracker.get_model_breakdown()

    # Should be sorted by cost (descending)
    assert len(breakdown) == 3
    assert breakdown[0]["model"] == "claude-opus-4-5"
    assert breakdown[1]["model"] == "claude-sonnet-4-5"
    assert breakdown[2]["model"] == "claude-haiku-4-5"

    # Check structure of each entry
    for entry in breakdown:
        assert "model" in entry
        assert "cost_usd" in entry
        assert "input_tokens" in entry
        assert "output_tokens" in entry
        assert "calls" in entry
        assert "avg_cost_per_call" in entry

        # Check values
        assert entry["input_tokens"] == 10000
        assert entry["output_tokens"] == 5000
        assert entry["calls"] == 1
        assert entry["avg_cost_per_call"] == entry["cost_usd"]


def test_reset_functionality():
    """Test reset functionality."""
    tracker = CostTracker(budget_limit=1.0)

    # Make some calls
    tracker.track("claude-sonnet-4-5", 1000, 500)
    tracker.track("claude-haiku-4-5", 2000, 1000)

    # Reset and check returned stats
    stats = tracker.reset()
    assert stats["total_calls"] == 2
    assert stats["session_total_usd"] > 0

    # Check tracker is cleared
    assert tracker.total_cost == 0
    assert tracker.total_calls == 0
    assert len(tracker._costs) == 0
    assert len(tracker._token_counts) == 0
    assert len(tracker._call_counts) == 0

    # Budget should remain
    assert tracker.budget_limit == 1.0


def test_multiple_models():
    """Test tracking multiple models simultaneously."""
    tracker = CostTracker()

    # Track different models
    models = [
        ("claude-opus-4-5", 1000, 500),
        ("claude-sonnet-4-5", 2000, 1000),
        ("claude-haiku-4-5", 3000, 1500),
        ("text-embedding-3-small", 10000, 0),
        ("voyage-code-3", 5000, 0),
    ]

    total_expected_cost = 0
    for model, input_tokens, output_tokens in models:
        cost = tracker.track(model, input_tokens, output_tokens)
        total_expected_cost += cost

    # Check total cost
    assert abs(tracker.total_cost - total_expected_cost) < 1e-9

    # Check all models are tracked
    assert len(tracker._costs) == 5
    assert len(tracker._token_counts) == 5
    assert len(tracker._call_counts) == 5


def test_unknown_model_defaults():
    """Test that unknown models default to zero cost."""
    tracker = CostTracker()

    # Track unknown model
    cost = tracker.track("unknown-model", 10000, 5000)

    assert cost == 0.0
    assert tracker.total_cost == 0.0


def test_set_budget():
    """Test setting and updating budget."""
    tracker = CostTracker()

    # Initially no budget
    assert tracker.budget_limit is None

    # Set budget
    tracker.set_budget(0.5)
    assert tracker.budget_limit == 0.5

    # Update budget
    tracker.set_budget(1.0)
    assert tracker.budget_limit == 1.0

    # Clear budget
    tracker.set_budget(None)
    assert tracker.budget_limit is None


def test_get_model_pricing():
    """Test static method to get model pricing."""
    # Known model
    pricing = CostTracker.get_model_pricing("claude-sonnet-4-5")
    assert pricing == (3.0, 15.0)

    # Unknown model
    pricing = CostTracker.get_model_pricing("unknown-model")
    assert pricing == (0.0, 0.0)


def test_estimate_cost():
    """Test static method to estimate cost without tracking."""
    # Estimate without tracking
    cost = CostTracker.estimate_cost("claude-sonnet-4-5", 1000, 500)

    # Expected: 1000 * 3.0/1M + 500 * 15.0/1M = 0.003 + 0.0075 = 0.0105
    expected_cost = 0.0105
    assert abs(cost - expected_cost) < 1e-9

    # Verify it didn't track
    tracker = CostTracker()
    assert tracker.total_cost == 0.0


def test_zero_duration_edge_case():
    """Test that zero duration doesn't cause division by zero."""
    tracker = CostTracker()

    # Get stats immediately (duration ~0)
    stats = tracker.get_stats()

    # Should handle gracefully
    assert stats["cost_per_minute_usd"] == 0


def test_embedding_models():
    """Test cost tracking for embedding models."""
    tracker = CostTracker()

    # Track embedding calls (no output tokens)
    tracker.track("text-embedding-3-small", 10000, 0)
    tracker.track("voyage-code-3", 20000, 0)
    tracker.track("nomic-embed-text", 50000, 0)  # Free local model

    # Check costs
    assert tracker._costs["text-embedding-3-small"] > 0
    assert tracker._costs["voyage-code-3"] > 0
    assert tracker._costs.get("nomic-embed-text", 0) == 0  # Free


def test_large_token_counts():
    """Test handling of large token counts."""
    tracker = CostTracker(budget_limit=100.0)  # Higher budget to allow the call

    # Track a very large call
    cost = tracker.track("claude-opus-4-5", 1_000_000, 500_000)

    # Expected: 1M * 15/1M + 500k * 75/1M = 15 + 37.5 = 52.5
    expected_cost = 52.5
    assert abs(cost - expected_cost) < 1e-6

    # Should be under budget
    assert tracker.total_cost < tracker.budget_limit

    # But a second call would exceed
    with pytest.raises(BudgetExceededError):
        tracker.track("claude-opus-4-5", 1_000_000, 500_000)


def test_budget_edge_cases():
    """Test edge cases for budget handling."""
    # Zero budget
    tracker = CostTracker(budget_limit=0.0)
    with pytest.raises(BudgetExceededError):
        tracker.track("claude-haiku-4-5", 1, 1)

    # Negative budget (should still work, just always exceeded)
    tracker = CostTracker(budget_limit=-1.0)
    with pytest.raises(BudgetExceededError):
        tracker.track("claude-haiku-4-5", 1, 1)


def test_model_pricing_constants():
    """Test that all model pricing constants are valid."""
    for model, (input_price, output_price) in MODEL_PRICING.items():
        assert input_price >= 0, f"{model} has negative input price"
        assert output_price >= 0, f"{model} has negative output price"

        # For embedding models, output should be 0
        if "embedding" in model or "embed" in model:
            assert output_price == 0, f"{model} embedding model has output price"
