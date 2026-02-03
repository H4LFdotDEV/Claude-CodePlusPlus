#!/usr/bin/env python3
"""Demo of the Model Router for intelligent model selection."""

from memory_mcp import ModelRouter, TaskComplexity


def main():
    """Demonstrate model router capabilities."""
    router = ModelRouter()

    print("=" * 80)
    print("Model Router Demo - Intelligent Task Classification")
    print("=" * 80)
    print()

    # Test various tasks
    tasks = [
        # Simple tasks (Haiku)
        ("what is the capital of France?", TaskComplexity.SIMPLE),
        ("list all memories", TaskComplexity.SIMPLE),
        ("get user preferences", TaskComplexity.SIMPLE),
        ("show me recent files", TaskComplexity.SIMPLE),

        # Standard tasks (Sonnet)
        ("write a function to parse JSON data", TaskComplexity.STANDARD),
        ("create a user registration endpoint", TaskComplexity.STANDARD),
        ("fix the bug in the login flow", TaskComplexity.STANDARD),
        ("add validation to the form", TaskComplexity.STANDARD),

        # Complex tasks (Opus)
        ("architect a new microservices system", TaskComplexity.COMPLEX),
        ("design system for user management", TaskComplexity.COMPLEX),
        ("security review of the API endpoints", TaskComplexity.COMPLEX),
        ("optimize performance of the query engine", TaskComplexity.COMPLEX),
    ]

    print("Task Classification Results:")
    print("-" * 80)

    for task, expected in tasks:
        model = router.route(task)
        complexity = router.classify(task)

        status = "✓" if complexity == expected else "✗"
        print(f"{status} {task[:50]:<50} → {model}")

    print()
    print("-" * 80)
    print()

    # Show statistics
    stats = router.get_stats()
    print("Routing Statistics:")
    print(f"  Total routes: {stats['total_routes']}")
    print(f"  Distribution:")
    for complexity, count in stats['by_complexity'].items():
        pct = stats['distribution'][complexity] * 100
        print(f"    {complexity}: {count} ({pct:.1f}%)")

    print()

    # Show cost savings
    savings = router.estimate_savings()
    print("Cost Savings Analysis (vs. always using Sonnet):")
    print(f"  Simple tasks routed: {savings['simple_tasks_routed']}")
    print(f"  Baseline cost: ${savings['baseline_cost_usd']:.4f}")
    print(f"  Routed cost: ${savings['routed_cost_usd']:.4f}")
    print(f"  Savings: ${savings['savings_usd']:.4f} ({savings['savings_percent']:.1f}%)")

    print()
    print("=" * 80)

    # Demonstrate cost estimation
    print()
    print("Cost Estimation Examples (per 1000 input, 500 output tokens):")
    print("-" * 80)

    models = [
        ("claude-haiku-4-5", "Haiku"),
        ("claude-sonnet-4-5", "Sonnet"),
        ("claude-opus-4-5", "Opus"),
    ]

    for model, name in models:
        cost = router.estimate_cost(model, 1000, 500)
        print(f"  {name}: ${cost:.6f}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
