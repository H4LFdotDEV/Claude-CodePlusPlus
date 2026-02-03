"""Cost Tracker for API usage monitoring."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


class BudgetExceededError(Exception):
    """Raised when session budget is exceeded."""
    pass


# Pricing per 1M tokens (input, output)
MODEL_PRICING = {
    # Claude models
    "claude-opus-4-5": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.25, 1.25),
    # Embedding models
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "voyage-code-3": (0.06, 0.0),
    "nomic-embed-text": (0.0, 0.0),  # Local, free
}


@dataclass
class CostTracker:
    """Track API costs across a session."""

    budget_limit: Optional[float] = None
    session_start: datetime = field(default_factory=datetime.now)
    _costs: Dict[str, float] = field(default_factory=dict)
    _token_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    _call_counts: Dict[str, int] = field(default_factory=dict)

    def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
        raise_on_budget: bool = True
    ) -> float:
        """Track a model call and return the cost.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            raise_on_budget: If True, raise BudgetExceededError when over budget

        Returns:
            Cost of this call in USD
        """
        pricing = MODEL_PRICING.get(model, (0.0, 0.0))
        cost = (
            input_tokens * pricing[0] / 1_000_000 +
            output_tokens * pricing[1] / 1_000_000
        )

        # Update costs
        self._costs[model] = self._costs.get(model, 0.0) + cost

        # Update token counts
        if model not in self._token_counts:
            self._token_counts[model] = {"input": 0, "output": 0}
        self._token_counts[model]["input"] += input_tokens
        self._token_counts[model]["output"] += output_tokens

        # Update call counts
        self._call_counts[model] = self._call_counts.get(model, 0) + 1

        # Check budget
        if raise_on_budget and self.budget_limit is not None:
            if self.total_cost > self.budget_limit:
                raise BudgetExceededError(
                    f"Session cost ${self.total_cost:.4f} exceeds "
                    f"budget ${self.budget_limit:.4f}"
                )

        return cost

    @property
    def total_cost(self) -> float:
        """Get total session cost in USD."""
        return sum(self._costs.values())

    @property
    def total_tokens(self) -> Dict[str, int]:
        """Get total token counts across all models."""
        totals = {"input": 0, "output": 0}
        for counts in self._token_counts.values():
            totals["input"] += counts["input"]
            totals["output"] += counts["output"]
        return totals

    @property
    def total_calls(self) -> int:
        """Get total number of API calls."""
        return sum(self._call_counts.values())

    @property
    def budget_remaining(self) -> Optional[float]:
        """Get remaining budget in USD, or None if no budget set."""
        if self.budget_limit is None:
            return None
        return max(0, self.budget_limit - self.total_cost)

    @property
    def budget_percent_used(self) -> Optional[float]:
        """Get percentage of budget used, or None if no budget set."""
        if self.budget_limit is None or self.budget_limit == 0:
            return None
        return min(100, (self.total_cost / self.budget_limit) * 100)

    def get_stats(self) -> dict:
        """Get comprehensive cost statistics."""
        session_duration = (datetime.now() - self.session_start).total_seconds()

        return {
            "session_total_usd": round(self.total_cost, 6),
            "by_model": {k: round(v, 6) for k, v in self._costs.items()},
            "token_counts": self._token_counts.copy(),
            "total_tokens": self.total_tokens,
            "call_counts": self._call_counts.copy(),
            "total_calls": self.total_calls,
            "budget_limit_usd": self.budget_limit,
            "budget_remaining_usd": (
                round(self.budget_remaining, 6)
                if self.budget_remaining is not None else None
            ),
            "budget_percent_used": (
                round(self.budget_percent_used, 2)
                if self.budget_percent_used is not None else None
            ),
            "session_duration_seconds": round(session_duration, 2),
            "cost_per_minute_usd": (
                round(self.total_cost / (session_duration / 60), 6)
                if session_duration > 0 else 0
            ),
        }

    def get_model_breakdown(self) -> list:
        """Get cost breakdown by model, sorted by cost."""
        breakdown = []
        for model in self._costs:
            cost = self._costs[model]
            tokens = self._token_counts.get(model, {"input": 0, "output": 0})
            calls = self._call_counts.get(model, 0)

            breakdown.append({
                "model": model,
                "cost_usd": round(cost, 6),
                "input_tokens": tokens["input"],
                "output_tokens": tokens["output"],
                "calls": calls,
                "avg_cost_per_call": round(cost / calls, 6) if calls > 0 else 0,
            })

        return sorted(breakdown, key=lambda x: x["cost_usd"], reverse=True)

    def reset(self) -> dict:
        """Reset the tracker and return final stats."""
        stats = self.get_stats()
        self._costs.clear()
        self._token_counts.clear()
        self._call_counts.clear()
        self.session_start = datetime.now()
        return stats

    def set_budget(self, limit: Optional[float]) -> None:
        """Set or update the budget limit."""
        self.budget_limit = limit

    @staticmethod
    def get_model_pricing(model: str) -> tuple:
        """Get pricing for a model (input, output per 1M tokens)."""
        return MODEL_PRICING.get(model, (0.0, 0.0))

    @staticmethod
    def estimate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int = 0
    ) -> float:
        """Estimate cost for a model call without tracking."""
        pricing = MODEL_PRICING.get(model, (0.0, 0.0))
        return (
            input_tokens * pricing[0] / 1_000_000 +
            output_tokens * pricing[1] / 1_000_000
        )
