# cost_tracker.py
# API cost tracking with budget management and thread-safety
# Jeremiah Kroesche | Halfservers LLC

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when session budget limit is exceeded.

    Attributes:
        total_cost: The total cost when budget was exceeded
        budget_limit: The configured budget limit
    """

    def __init__(self, message: str, total_cost: float = 0.0, budget_limit: float = 0.0):
        super().__init__(message)
        self.total_cost = total_cost
        self.budget_limit = budget_limit


# Pricing per 1M tokens: (input_cost, output_cost)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # Claude models (using actual API model IDs)
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.80, 4.00),

    # Embedding models (output cost is 0.0 for embeddings)
    "text-embedding-3-small": (0.02, 0.0),
    "voyage-code-3": (0.06, 0.0),
    "nomic-embed-text": (0.0, 0.0),  # Local/free
}


@dataclass
class CostTracker:
    """Thread-safe API cost tracker with budget management.

    Tracks token usage and costs across multiple models with optional
    budget enforcement. All methods are thread-safe via internal locking.

    Attributes:
        budget_limit: Optional maximum budget in USD. When exceeded,
            track() raises BudgetExceededError.
        session_start: When this tracker was created (for duration stats).

    Example:
        tracker = CostTracker(budget_limit=1.0)

        try:
            cost = tracker.track("claude-sonnet-4-20250514", 1000, 500)
            print(f"Call cost: ${cost:.6f}")
        except BudgetExceededError as e:
            print(f"Over budget: {e}")

        stats = tracker.get_stats()
        print(f"Session total: ${stats['session_total_usd']}")
    """

    budget_limit: Optional[float] = None
    session_start: datetime = field(default_factory=datetime.now)
    _costs: Dict[str, float] = field(default_factory=dict)
    _token_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
    ) -> float:
        """Track a model API call and return the cost.

        Thread-safe: Uses internal locking for all state updates.

        Args:
            model: Model identifier (e.g., "claude-sonnet-4-20250514")
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated (default 0)

        Returns:
            Cost of this call in USD

        Raises:
            BudgetExceededError: If budget_limit is set and total_cost
                exceeds the limit after this call
        """
        pricing = MODEL_PRICING.get(model, (0.0, 0.0))
        cost = (
            input_tokens * pricing[0] / 1_000_000 +
            output_tokens * pricing[1] / 1_000_000
        )

        with self._lock:
            # Update costs
            self._costs[model] = self._costs.get(model, 0.0) + cost

            # Update token counts
            if model not in self._token_counts:
                self._token_counts[model] = {"input": 0, "output": 0}
            self._token_counts[model]["input"] += input_tokens
            self._token_counts[model]["output"] += output_tokens

            # Check budget after updating (so stats reflect the call that exceeded)
            current_total = sum(self._costs.values())
            if self.budget_limit is not None and current_total > self.budget_limit:
                raise BudgetExceededError(
                    f"Session cost ${current_total:.4f} exceeds budget ${self.budget_limit:.4f}",
                    total_cost=current_total,
                    budget_limit=self.budget_limit,
                )

        return cost

    @property
    def total_cost(self) -> float:
        """Get total session cost in USD.

        Thread-safe: Acquires lock for consistent read.

        Returns:
            Sum of all tracked costs
        """
        with self._lock:
            return sum(self._costs.values())

    def get_stats(self) -> Dict:
        """Get comprehensive cost statistics.

        Thread-safe: Acquires lock for consistent snapshot.

        Returns:
            Dictionary containing:
                - session_total_usd: Total cost this session
                - by_model: Cost breakdown by model
                - token_counts: Token usage by model
                - budget_remaining_usd: Remaining budget (or None)
                - session_duration_seconds: Time since session_start
        """
        with self._lock:
            total = sum(self._costs.values())
            session_duration = (datetime.now() - self.session_start).total_seconds()

            budget_remaining = None
            if self.budget_limit is not None:
                budget_remaining = round(max(0.0, self.budget_limit - total), 6)

            return {
                "session_total_usd": round(total, 6),
                "by_model": {k: round(v, 6) for k, v in self._costs.items()},
                "token_counts": {
                    model: counts.copy()
                    for model, counts in self._token_counts.items()
                },
                "budget_remaining_usd": budget_remaining,
                "session_duration_seconds": round(session_duration, 2),
            }

    def reset(self) -> Dict:
        """Reset tracker state and return final stats.

        Thread-safe: Acquires lock for atomic reset.

        Returns:
            Final stats before reset (same format as get_stats())
        """
        with self._lock:
            stats = self.get_stats()
            self._costs.clear()
            self._token_counts.clear()
            self.session_start = datetime.now()
            return stats

    @staticmethod
    def get_model_pricing(model: str) -> Tuple[float, float]:
        """Get pricing for a model.

        Args:
            model: Model identifier

        Returns:
            Tuple of (input_price, output_price) per 1M tokens.
            Returns (0.0, 0.0) for unknown models.
        """
        return MODEL_PRICING.get(model, (0.0, 0.0))

    @staticmethod
    def estimate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
    ) -> float:
        """Estimate cost for a model call without tracking.

        Useful for pre-flight cost checks before making API calls.

        Args:
            model: Model identifier
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens (default 0)

        Returns:
            Estimated cost in USD
        """
        pricing = MODEL_PRICING.get(model, (0.0, 0.0))
        return (
            input_tokens * pricing[0] / 1_000_000 +
            output_tokens * pricing[1] / 1_000_000
        )
