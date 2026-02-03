"""Example usage of LLM Response Caching."""

import asyncio
from memory_mcp.llm_cache import LLMResponseCache
from memory_mcp.redis_client import RedisClient


async def simulate_llm_call(prompt: str) -> str:
    """Simulate an LLM API call with delay."""
    await asyncio.sleep(0.1)  # Simulate network latency
    return f"LLM Response to: {prompt}"


async def main():
    # Initialize Redis client and cache
    redis_client = RedisClient(url="redis://localhost:6379")
    cache = LLMResponseCache(redis=redis_client, default_ttl=3600)

    print("=== LLM Response Caching Example ===\n")

    # Example 1: First call (cache miss, generates response)
    print("1. First call - Cache Miss")
    prompt1 = "What is the capital of France?"
    response1, was_cached1 = await cache.get_or_generate(
        prompt1,
        simulate_llm_call,
        model="sonnet"
    )
    print(f"   Prompt: {prompt1}")
    print(f"   Response: {response1}")
    print(f"   Was Cached: {was_cached1}")
    print()

    # Example 2: Second call (cache hit, instant)
    print("2. Second call - Cache Hit")
    response2, was_cached2 = await cache.get_or_generate(
        prompt1,
        simulate_llm_call,
        model="sonnet"
    )
    print(f"   Prompt: {prompt1}")
    print(f"   Response: {response2}")
    print(f"   Was Cached: {was_cached2}")
    print()

    # Example 3: Different prompt (cache miss)
    print("3. Different prompt - Cache Miss")
    prompt2 = "Explain quantum computing"
    response3, was_cached3 = await cache.get_or_generate(
        prompt2,
        simulate_llm_call,
        model="sonnet"
    )
    print(f"   Prompt: {prompt2}")
    print(f"   Response: {response3}")
    print(f"   Was Cached: {was_cached3}")
    print()

    # Example 4: Same prompt, different model (cache miss)
    print("4. Same prompt, different model - Cache Miss")
    response4, was_cached4 = await cache.get_or_generate(
        prompt1,
        simulate_llm_call,
        model="opus"
    )
    print(f"   Prompt: {prompt1}")
    print(f"   Model: opus")
    print(f"   Response: {response4}")
    print(f"   Was Cached: {was_cached4}")
    print()

    # Example 5: Cache statistics
    print("5. Cache Statistics")
    stats = cache.get_stats()
    print(f"   Hits: {stats['hits']}")
    print(f"   Misses: {stats['misses']}")
    print(f"   Stores: {stats['stores']}")
    print(f"   Hit Rate: {stats['hit_rate']:.2%}")
    print(f"   Redis Available: {stats['redis_available']}")
    print()

    # Example 6: Cost savings estimation
    print("6. Estimated Cost Savings")
    savings = cache.estimate_savings(cost_per_call=0.003)
    print(f"   Cache Hits: {savings['cache_hits']}")
    print(f"   Cost per Call: ${savings['cost_per_call_usd']:.3f}")
    print(f"   Estimated Savings: ${savings['estimated_savings_usd']:.3f}")
    print()

    # Example 7: Cache invalidation
    print("7. Cache Invalidation")
    print(f"   Before invalidation: {cache.get(prompt1, 'sonnet')}")
    cache.invalidate(prompt1, 'sonnet')
    print(f"   After invalidation: {cache.get(prompt1, 'sonnet')}")
    print()

    # Example 8: Clear all entries for a model
    print("8. Clear Model Cache")
    count = cache.clear_model("opus")
    print(f"   Cleared {count} entries for model 'opus'")
    print()

    # Example 9: Session Isolation
    print("9. Session Isolation")
    cache_session1 = LLMResponseCache(redis=redis_client, session_id="user-123")
    cache_session2 = LLMResponseCache(redis=redis_client, session_id="user-456")

    # Store same prompt in different sessions
    session_prompt = "What is the meaning of life?"
    response_s1, _ = await cache_session1.get_or_generate(
        session_prompt, simulate_llm_call
    )
    response_s2, _ = await cache_session2.get_or_generate(
        session_prompt, simulate_llm_call
    )

    print(f"   Session 1 (user-123): {response_s1}")
    print(f"   Session 2 (user-456): {response_s2}")
    print(f"   Sessions are isolated: {response_s1 != response_s2}")
    print()

    # Final statistics
    print("=== Final Statistics ===")
    final_stats = cache.get_stats()
    for key, value in final_stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
