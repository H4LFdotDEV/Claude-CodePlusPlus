"""Model Router for intelligent task-to-model routing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"      # Haiku - lookups, recalls, simple questions
    STANDARD = "standard"  # Sonnet - code gen, analysis, most tasks
    COMPLEX = "complex"    # Opus - architecture, deep reasoning


@dataclass
class ModelConfig:
    """Model configuration for each complexity level."""
    simple: str = "claude-haiku-4-5"
    standard: str = "claude-sonnet-4-5"
    complex: str = "claude-opus-4-5"

    # Cost per 1M tokens (input, output)
    costs: Dict[str, tuple] = field(default_factory=lambda: {
        "claude-opus-4-5": (15.0, 75.0),
        "claude-sonnet-4-5": (3.0, 15.0),
        "claude-haiku-4-5": (0.25, 1.25),
    })


class ModelRouter:
    """Routes tasks to appropriate models based on complexity."""

    # Patterns indicating simple tasks (Haiku)
    SIMPLE_PATTERNS = [
        "what is", "what's", "list", "show me", "show",
        "recall", "find", "get", "fetch", "retrieve",
        "lookup", "look up", "search for", "check",
        "tell me", "give me", "how many", "count",
    ]

    # Patterns indicating complex tasks (Opus)
    COMPLEX_PATTERNS = [
        "architect", "design system", "refactor entire", "optimize performance",
        "security review", "security audit", "plan migration", "strategy",
        "analyze root cause", "deep dive", "comprehensive review", "thorough analysis",
        "debug complex", "investigate", "root cause",
        "implement system", "build platform", "create distributed",
    ]

    # Context size thresholds
    LARGE_CONTEXT_THRESHOLD = 10000  # chars
    VERY_LARGE_CONTEXT_THRESHOLD = 50000  # chars

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self._stats = {
            TaskComplexity.SIMPLE: 0,
            TaskComplexity.STANDARD: 0,
            TaskComplexity.COMPLEX: 0,
        }

    def classify(
        self,
        task: str,
        context: Optional[dict] = None
    ) -> TaskComplexity:
        """Classify task complexity based on content and context."""
        task_lower = task.lower().strip()
        context_size = len(str(context)) if context else 0

        # Check for explicit complexity hints
        if any(hint in task_lower for hint in ["use opus", "deep thinking", "ultrathink"]):
            return TaskComplexity.COMPLEX

        # Check for complex patterns first (they're more specific)
        if any(pattern in task_lower for pattern in self.COMPLEX_PATTERNS):
            return TaskComplexity.COMPLEX

        # Check for simple hints (but not if complex patterns exist)
        if any(hint in task_lower for hint in ["quick", "fast"]):
            return TaskComplexity.SIMPLE

        # Context size influences complexity
        if context_size > self.VERY_LARGE_CONTEXT_THRESHOLD:
            return TaskComplexity.COMPLEX
        elif context_size > self.LARGE_CONTEXT_THRESHOLD:
            return TaskComplexity.STANDARD

        # Check for simple patterns
        if any(pattern in task_lower for pattern in self.SIMPLE_PATTERNS):
            # Short task with simple pattern = simple
            if len(task) < 100 and context_size < 1000:
                return TaskComplexity.SIMPLE

        # Task length heuristics (only for tasks without specific patterns)
        if len(task) > 500:
            return TaskComplexity.STANDARD
        elif len(task) < 20 and not any(pattern in task_lower for pattern in self.SIMPLE_PATTERNS):
            # Very short task without simple pattern - likely standard
            return TaskComplexity.STANDARD

        # Default to standard for most tasks
        return TaskComplexity.STANDARD

    def route(
        self,
        task: str,
        context: Optional[dict] = None
    ) -> str:
        """Route task to appropriate model."""
        complexity = self.classify(task, context)
        self._stats[complexity] += 1

        model_map = {
            TaskComplexity.SIMPLE: self.config.simple,
            TaskComplexity.STANDARD: self.config.standard,
            TaskComplexity.COMPLEX: self.config.complex,
        }

        return model_map[complexity]

    def get_model_cost(self, model: str) -> tuple:
        """Get cost per 1M tokens (input, output) for model."""
        return self.config.costs.get(model, (0.0, 0.0))

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0
    ) -> float:
        """Estimate cost for a model call."""
        costs = self.get_model_cost(model)
        return (
            input_tokens * costs[0] / 1_000_000 +
            output_tokens * costs[1] / 1_000_000
        )

    def get_stats(self) -> dict:
        """Get routing statistics."""
        total = sum(self._stats.values())
        return {
            "total_routes": total,
            "by_complexity": {
                k.value: v for k, v in self._stats.items()
            },
            "distribution": {
                k.value: round(v / total, 4) if total > 0 else 0
                for k, v in self._stats.items()
            },
        }

    def estimate_savings(self, baseline_model: str = "claude-sonnet-4-5") -> dict:
        """Estimate cost savings from intelligent routing."""
        baseline_cost = self.config.costs.get(baseline_model, (3.0, 15.0))
        simple_cost = self.config.costs.get(self.config.simple, (0.25, 1.25))

        # Assume average 1000 input, 500 output tokens per call
        avg_input, avg_output = 1000, 500

        simple_routes = self._stats[TaskComplexity.SIMPLE]

        # Cost if all simple tasks used baseline
        baseline_total = simple_routes * self.estimate_cost(
            baseline_model, avg_input, avg_output
        )

        # Actual cost with routing
        routed_total = simple_routes * self.estimate_cost(
            self.config.simple, avg_input, avg_output
        )

        savings = baseline_total - routed_total

        return {
            "simple_tasks_routed": simple_routes,
            "baseline_cost_usd": round(baseline_total, 4),
            "routed_cost_usd": round(routed_total, 4),
            "savings_usd": round(savings, 4),
            "savings_percent": round((savings / baseline_total * 100) if baseline_total > 0 else 0, 2),
        }
