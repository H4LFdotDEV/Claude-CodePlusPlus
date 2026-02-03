#!/usr/bin/env python3
"""
Example: Using Parallel Tier Search for Performance Optimization

This example demonstrates how to use the parallel tier search feature
to query all memory tiers concurrently, significantly improving search
performance compared to sequential searching.

Performance improvements:
- Sequential search: Sum of all tier latencies (e.g., 1ms + 50ms + 100ms = 151ms)
- Parallel search: Max of all tier latencies (e.g., max(1ms, 50ms, 100ms) = 100ms)
"""

import asyncio
from memory_mcp.tier_manager import TierManager
from memory_mcp.redis_client import RedisClient
from memory_mcp.graphiti_manager import GraphitiManager
from memory_mcp.sqlite_index import SQLiteIndex
from memory_mcp.vault_manager import VaultManager


async def main():
    """Demonstrate parallel tier search."""

    # Initialize tier components
    # In production, these would be properly configured
    redis_client = RedisClient(url="redis://localhost:6379")
    graphiti = GraphitiManager()
    sqlite_index = SQLiteIndex()
    vault = VaultManager()

    # Create tier manager with all tiers
    tier_manager = TierManager(
        redis=redis_client,
        graphiti=graphiti,
        sqlite=sqlite_index,
        vault=vault
    )

    # Example 1: Search all tiers in parallel
    print("Example 1: Search all tiers in parallel")
    results = await tier_manager.search_all_tiers_parallel(
        query="authentication",
        limit=10
    )

    print(f"Found {len(results)} results:")
    for result in results:
        tier = result.get('_source_tier', 'unknown')
        score = result.get('score', 0)
        content_preview = result.get('content', '')[:100]
        print(f"  [{tier}] Score: {score:.2f} - {content_preview}...")

    # Example 2: Search specific tiers only
    print("\nExample 2: Search only hot and warm tiers")
    results = await tier_manager.search_all_tiers_parallel(
        query="authentication",
        limit=10,
        tiers=['hot', 'warm']  # Only search fast tiers
    )

    print(f"Found {len(results)} results from fast tiers")

    # Example 3: Compare with sequential search
    print("\nExample 3: Performance comparison")

    import time

    # Parallel search
    start = time.time()
    parallel_results = await tier_manager.search_all_tiers_parallel(
        query="user preferences",
        limit=20
    )
    parallel_time = time.time() - start

    # Sequential search (existing method)
    start = time.time()
    sequential_results = tier_manager.search_all_tiers(
        query="user preferences",
        limit=20
    )
    sequential_time = time.time() - start

    print(f"Parallel search: {parallel_time*1000:.1f}ms ({len(parallel_results)} results)")
    print(f"Sequential search: {sequential_time*1000:.1f}ms ({len(sequential_results)} results)")

    if sequential_time > 0:
        speedup = sequential_time / parallel_time
        print(f"Speedup: {speedup:.1f}x faster")

    # Example 4: Graceful degradation
    print("\nExample 4: Graceful degradation (one tier fails)")

    # Create manager with only some tiers available
    partial_manager = TierManager(
        redis=None,  # Redis not available
        graphiti=graphiti,
        sqlite=sqlite_index
    )

    results = await partial_manager.search_all_tiers_parallel(
        query="error handling",
        limit=10
    )

    print(f"Found {len(results)} results even without Redis tier")
    tiers_used = {r.get('_source_tier') for r in results}
    print(f"Tiers used: {tiers_used}")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

    print("\n" + "="*60)
    print("Parallel Search Best Practices:")
    print("="*60)
    print("1. Use parallel search for all user-facing queries")
    print("2. Filter tiers when you know where data lives")
    print("3. Set appropriate limits to control result size")
    print("4. Parallel search handles tier failures gracefully")
    print("5. Results are automatically deduplicated by ID")
    print("6. Results are sorted by relevance score")
