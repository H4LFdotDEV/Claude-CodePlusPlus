"""Tests for model router."""

import pytest
from shared.model_router import ModelRouter, TaskComplexity, ModelConfig


class TestModelRouter:
    """Test suite for ModelRouter."""

    def setup_method(self):
        """Setup for each test."""
        self.router = ModelRouter()

    def test_simple_task_classification(self):
        """Test that simple tasks are classified correctly."""
        simple_tasks = [
            "what is the capital of France?",
            "list all memories",
            "show me recent files",
            "get user preferences",
            "find document by ID",
            "recall my last session",
            "lookup authentication token",
            "tell me about the project",
            "how many tasks are pending?",
            "count the errors",
        ]

        for task in simple_tasks:
            complexity = self.router.classify(task)
            assert complexity == TaskComplexity.SIMPLE, f"Failed for: {task}"

    def test_complex_task_classification(self):
        """Test that complex tasks are classified correctly."""
        complex_tasks = [
            "architect a new microservices system",
            "design system for user management",
            "refactor entire authentication module",
            "optimize performance of the query engine",
            "security review of the API endpoints",
            "security audit the codebase",
            "plan migration strategy",
            "analyze root cause of the memory leak",
            "implement system for logging",
            "build platform for distributed caching",
        ]

        for task in complex_tasks:
            complexity = self.router.classify(task)
            assert complexity == TaskComplexity.COMPLEX, f"Failed for: {task}"

    def test_standard_task_classification(self):
        """Test that standard tasks default correctly."""
        standard_tasks = [
            "write a function to parse JSON",
            "create a user registration endpoint",
            "fix the bug in the login flow",
            "add validation to the form",
            "update the documentation",
        ]

        for task in standard_tasks:
            complexity = self.router.classify(task)
            assert complexity == TaskComplexity.STANDARD, f"Failed for: {task}"

    def test_explicit_complexity_hints(self):
        """Test explicit complexity hints override patterns."""
        # Explicit complex hint
        assert self.router.classify("use opus to list files") == TaskComplexity.COMPLEX
        assert self.router.classify("deep thinking needed for simple lookup") == TaskComplexity.COMPLEX
        assert self.router.classify("ultrathink about what is X") == TaskComplexity.COMPLEX

        # Explicit simple hint (without complex patterns)
        assert self.router.classify("quick lookup of user data") == TaskComplexity.SIMPLE
        assert self.router.classify("fast fetch of records") == TaskComplexity.SIMPLE

    def test_context_size_influences_complexity(self):
        """Test that context size affects classification."""
        task = "summarize the content"

        # Small context - could be simple
        small_context = {"data": "x" * 100}
        complexity = self.router.classify(task, small_context)
        # Should be SIMPLE or STANDARD
        assert complexity in [TaskComplexity.SIMPLE, TaskComplexity.STANDARD]

        # Large context - standard
        large_context = {"data": "x" * 15000}
        complexity = self.router.classify(task, large_context)
        assert complexity == TaskComplexity.STANDARD

        # Very large context - complex
        very_large_context = {"data": "x" * 60000}
        complexity = self.router.classify(task, very_large_context)
        assert complexity == TaskComplexity.COMPLEX

    def test_task_length_heuristics(self):
        """Test that task length affects classification."""
        # Very short task
        short_task = "list"
        assert self.router.classify(short_task) == TaskComplexity.SIMPLE

        # Long task
        long_task = "x" * 600
        assert self.router.classify(long_task) == TaskComplexity.STANDARD

    def test_routing_returns_correct_models(self):
        """Test that routing returns appropriate model names."""
        # Simple task
        model = self.router.route("what is X?")
        assert model == "claude-haiku-4-5"

        # Complex task
        model = self.router.route("architect a system")
        assert model == "claude-opus-4-5"

        # Standard task - make it longer to avoid simple classification
        model = self.router.route("write a function to handle user authentication")
        assert model == "claude-sonnet-4-5"

    def test_stats_tracking(self):
        """Test that routing statistics are tracked correctly."""
        # Initial stats
        stats = self.router.get_stats()
        assert stats["total_routes"] == 0

        # Route some tasks
        self.router.route("what is X?")  # simple
        self.router.route("what is Y?")  # simple
        self.router.route("architect a system")  # complex
        self.router.route("write code to handle authentication and validation")  # standard

        # Check stats
        stats = self.router.get_stats()
        assert stats["total_routes"] == 4
        assert stats["by_complexity"]["simple"] == 2
        assert stats["by_complexity"]["complex"] == 1
        assert stats["by_complexity"]["standard"] == 1
        assert stats["distribution"]["simple"] == 0.5

    def test_cost_estimation(self):
        """Test cost estimation calculations."""
        # Haiku cost
        cost = self.router.estimate_cost("claude-haiku-4-5", 1000, 500)
        expected = (1000 * 0.25 / 1_000_000) + (500 * 1.25 / 1_000_000)
        assert abs(cost - expected) < 0.0001

        # Sonnet cost
        cost = self.router.estimate_cost("claude-sonnet-4-5", 1000, 500)
        expected = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001

        # Opus cost
        cost = self.router.estimate_cost("claude-opus-4-5", 1000, 500)
        expected = (1000 * 15.0 / 1_000_000) + (500 * 75.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_savings_estimation(self):
        """Test cost savings estimation."""
        # Route some simple tasks
        self.router.route("what is X?")
        self.router.route("list items")
        self.router.route("show me")

        savings = self.router.estimate_savings()

        assert savings["simple_tasks_routed"] == 3
        assert savings["baseline_cost_usd"] > 0
        assert savings["routed_cost_usd"] > 0
        assert savings["savings_usd"] > 0
        assert savings["baseline_cost_usd"] > savings["routed_cost_usd"]
        assert savings["savings_percent"] > 0

    def test_custom_model_config(self):
        """Test router with custom model configuration."""
        custom_config = ModelConfig(
            simple="custom-haiku",
            standard="custom-sonnet",
            complex="custom-opus",
            costs={
                "custom-haiku": (0.1, 0.5),
                "custom-sonnet": (1.0, 5.0),
                "custom-opus": (10.0, 50.0),
            }
        )

        router = ModelRouter(config=custom_config)

        # Test routing
        assert router.route("what is X?") == "custom-haiku"
        assert router.route("write code to implement the feature properly") == "custom-sonnet"
        assert router.route("architect system") == "custom-opus"

        # Test cost estimation
        cost = router.estimate_cost("custom-haiku", 1000, 500)
        expected = (1000 * 0.1 / 1_000_000) + (500 * 0.5 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_get_model_cost(self):
        """Test retrieving model costs."""
        haiku_cost = self.router.get_model_cost("claude-haiku-4-5")
        assert haiku_cost == (0.25, 1.25)

        sonnet_cost = self.router.get_model_cost("claude-sonnet-4-5")
        assert sonnet_cost == (3.0, 15.0)

        opus_cost = self.router.get_model_cost("claude-opus-4-5")
        assert opus_cost == (15.0, 75.0)

        # Unknown model
        unknown_cost = self.router.get_model_cost("unknown-model")
        assert unknown_cost == (0.0, 0.0)

    def test_simple_pattern_with_long_context(self):
        """Test that simple patterns with large context don't stay simple."""
        task = "what is the value?"
        large_context = {"data": "x" * 20000}

        # Should be upgraded to STANDARD due to large context
        complexity = self.router.classify(task, large_context)
        assert complexity == TaskComplexity.STANDARD

    def test_edge_cases(self):
        """Test edge cases."""
        # Empty task
        assert self.router.classify("") == TaskComplexity.STANDARD

        # None context
        assert self.router.classify("some task here", None) == TaskComplexity.STANDARD

        # Empty context
        assert self.router.classify("some task here", {}) == TaskComplexity.STANDARD

        # Task with multiple patterns
        task = "architect and design system for user lookup"
        # "architect" and "design system" patterns should win
        assert self.router.classify(task) == TaskComplexity.COMPLEX


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
