# model_router.py
# Intelligent model routing based on task complexity
# Jeremiah Kroesche | Halfservers LLC
#
# Routes tasks to appropriate Claude models based on:
# - Task complexity classification (simple, standard, complex)
# - Context size
# - Pattern matching for common task types

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory_mcp")


class TaskComplexity(Enum):
    """Classification of task complexity for model selection.

    SIMPLE: Quick lookups, recalls, simple queries
        - Uses Haiku for cost efficiency
        - Target latency: <1s

    STANDARD: Code generation, analysis, typical development tasks
        - Uses Sonnet as the balanced choice
        - Target latency: <5s

    COMPLEX: Architecture, deep reasoning, security reviews
        - Uses Opus for maximum capability
        - Target latency: <30s
    """

    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


@dataclass
class ModelConfig:
    """Configuration for model selection by complexity tier.

    Attributes:
        simple: Model ID for simple tasks (fast, low cost)
        standard: Model ID for standard tasks (balanced)
        complex: Model ID for complex tasks (maximum capability)
        context_threshold_complex: Context size (chars) that triggers complex classification
    """

    simple: str = "claude-3-5-haiku-20241022"
    standard: str = "claude-sonnet-4-20250514"
    complex: str = "claude-opus-4-20250514"
    context_threshold_complex: int = 10000


@dataclass
class ClassificationResult:
    """Result of task complexity classification.

    Attributes:
        complexity: The determined complexity level
        model: The selected model ID
        reason: Human-readable explanation of classification
        matched_pattern: The pattern that triggered classification (if any)
    """

    complexity: TaskComplexity
    model: str
    reason: str
    matched_pattern: Optional[str] = None


class ModelRouter:
    """Routes tasks to appropriate Claude models based on complexity.

    The router uses a combination of pattern matching and heuristics to
    classify tasks and select the most appropriate model:

    1. Simple tasks (Haiku): Quick lookups, recalls, basic queries
    2. Standard tasks (Sonnet): Code generation, analysis, typical work
    3. Complex tasks (Opus): Architecture, deep reasoning, security

    Example:
        >>> router = ModelRouter()
        >>> model = router.route("list all memory entries")
        >>> print(model)  # claude-3-5-haiku-20241022

        >>> model = router.route("design a microservices architecture")
        >>> print(model)  # claude-opus-4-20250514
    """

    # Patterns indicating simple tasks (lookups, recalls)
    SIMPLE_PATTERNS: List[str] = [
        "list",
        "show",
        "recall",
        "find",
        "get",
        "fetch",
        "retrieve",
        "lookup",
        "what is",
        "what are",
        "show me",
        "display",
        "count",
        "status",
    ]

    # Patterns indicating complex tasks (deep reasoning required)
    COMPLEX_PATTERNS: List[str] = [
        "architect",
        "design",
        "refactor",
        "optimize",
        "security review",
        "security audit",
        "plan",
        "strategy",
        "analyze architecture",
        "redesign",
        "migrate",
        "scale",
        "evaluate tradeoffs",
        "compare approaches",
        "long-term",
        "comprehensive review",
    ]

    # Minimum task length to consider for simple classification
    # Very short tasks are likely simple queries
    MIN_LENGTH_FOR_STANDARD: int = 100

    def __init__(self, config: Optional[ModelConfig] = None):
        """Initialize the model router.

        Args:
            config: Optional model configuration. Uses defaults if not provided.
        """
        self.config = config or ModelConfig()

    def classify(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """Classify task complexity and determine appropriate model.

        The classification process:
        1. Check for complex patterns first (highest priority)
        2. Check context size (large context = complex)
        3. Check for simple patterns with short task length
        4. Default to standard for ambiguous cases

        Args:
            task: The task description or prompt
            context: Optional context dict (files, history, etc.)

        Returns:
            ClassificationResult with complexity, model, and reasoning
        """
        task_lower = task.lower().strip()
        context_size = len(str(context)) if context else 0

        # Check for complex patterns first (highest priority)
        for pattern in self.COMPLEX_PATTERNS:
            if pattern in task_lower:
                return ClassificationResult(
                    complexity=TaskComplexity.COMPLEX,
                    model=self.config.complex,
                    reason=f"Task matches complex pattern: '{pattern}'",
                    matched_pattern=pattern
                )

        # Large context triggers complex classification
        if context_size > self.config.context_threshold_complex:
            return ClassificationResult(
                complexity=TaskComplexity.COMPLEX,
                model=self.config.complex,
                reason=f"Context size ({context_size:,} chars) exceeds threshold ({self.config.context_threshold_complex:,})",
                matched_pattern=None
            )

        # Check for simple patterns (with length constraint)
        # Short tasks with simple patterns are classified as simple
        if len(task) < self.MIN_LENGTH_FOR_STANDARD:
            for pattern in self.SIMPLE_PATTERNS:
                if pattern in task_lower:
                    # Verify no complex indicators present
                    has_complex_indicator = any(
                        cp in task_lower for cp in self.COMPLEX_PATTERNS
                    )
                    if not has_complex_indicator:
                        return ClassificationResult(
                            complexity=TaskComplexity.SIMPLE,
                            model=self.config.simple,
                            reason=f"Short task matches simple pattern: '{pattern}'",
                            matched_pattern=pattern
                        )

        # Default to standard for ambiguous cases
        return ClassificationResult(
            complexity=TaskComplexity.STANDARD,
            model=self.config.standard,
            reason="No specific pattern matched; defaulting to standard complexity",
            matched_pattern=None
        )

    def route(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Route task to appropriate model.

        Convenience method that returns just the model ID.
        Use `classify()` for detailed classification information.

        Args:
            task: The task description or prompt
            context: Optional context dict (files, history, etc.)

        Returns:
            Model ID string (e.g., "claude-sonnet-4-20250514")
        """
        result = self.classify(task, context)
        logger.debug(
            f"Routed task to {result.model} "
            f"(complexity={result.complexity.value}, reason={result.reason})"
        )
        return result.model

    def get_model_for_complexity(self, complexity: TaskComplexity) -> str:
        """Get the model ID for a specific complexity level.

        Args:
            complexity: The desired complexity level

        Returns:
            Model ID for the specified complexity
        """
        return {
            TaskComplexity.SIMPLE: self.config.simple,
            TaskComplexity.STANDARD: self.config.standard,
            TaskComplexity.COMPLEX: self.config.complex,
        }[complexity]

    def override_route(
        self,
        task: str,
        forced_complexity: TaskComplexity,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Route with forced complexity override.

        Useful when the caller knows the task requires a specific
        complexity level regardless of pattern matching.

        Args:
            task: The task description (logged but not classified)
            forced_complexity: The complexity level to use
            context: Optional context (ignored for routing but logged)

        Returns:
            Model ID for the forced complexity level
        """
        model = self.get_model_for_complexity(forced_complexity)
        logger.debug(
            f"Forced route to {model} "
            f"(override to {forced_complexity.value})"
        )
        return model

    def estimate_cost_factor(self, complexity: TaskComplexity) -> float:
        """Estimate relative cost factor for a complexity level.

        Returns approximate cost multiplier relative to Haiku.
        Useful for cost tracking and budget decisions.

        Args:
            complexity: The complexity level

        Returns:
            Cost multiplier (1.0 = Haiku baseline)
        """
        # Based on approximate pricing ratios
        # Haiku: $0.25/1M input, $1.25/1M output
        # Sonnet: $3/1M input, $15/1M output (~12x Haiku)
        # Opus: $15/1M input, $75/1M output (~60x Haiku)
        return {
            TaskComplexity.SIMPLE: 1.0,
            TaskComplexity.STANDARD: 12.0,
            TaskComplexity.COMPLEX: 60.0,
        }[complexity]
