"""Example: Integrating LLM Cache with Memory MCP handlers."""

import asyncio
from typing import Optional

from memory_mcp.llm_cache import LLMResponseCache
from memory_mcp.redis_client import RedisClient


class MockLLMClient:
    """Mock LLM client for demonstration."""

    def __init__(self, cache: Optional[LLMResponseCache] = None):
        self.cache = cache
        self.api_calls = 0

    async def generate_embedding_description(self, content: str, model: str = "sonnet") -> str:
        """Generate natural language description of content for embeddings."""
        prompt = f"Describe this content concisely for semantic search:\n\n{content}"

        if self.cache:
            response, was_cached = await self.cache.get_or_generate(
                prompt=prompt,
                generator=self._call_api,
                model=model,
                ttl=7200  # 2 hours - embeddings descriptions are stable
            )
            if not was_cached:
                self.api_calls += 1
            return response
        else:
            return await self._call_api(prompt)

    async def generate_summary(self, content: str, model: str = "sonnet") -> str:
        """Generate summary of content."""
        prompt = f"Summarize this content in 2-3 sentences:\n\n{content}"

        if self.cache:
            response, was_cached = await self.cache.get_or_generate(
                prompt=prompt,
                generator=self._call_api,
                model=model,
                ttl=3600  # 1 hour - summaries can be cached
            )
            if not was_cached:
                self.api_calls += 1
            return response
        else:
            return await self._call_api(prompt)

    async def _call_api(self, prompt: str) -> str:
        """Simulate LLM API call."""
        await asyncio.sleep(0.1)  # Simulate network latency
        self.api_calls += 1
        return f"[Generated response for: {prompt[:50]}...]"


async def demo_without_cache():
    """Demonstrate LLM calls without caching."""
    print("=== Without Cache ===\n")

    client = MockLLMClient(cache=None)
    content = "Python is a high-level programming language."

    # Multiple calls - all hit API
    for i in range(3):
        await client.generate_embedding_description(content)
        await client.generate_summary(content)

    print(f"Total API calls: {client.api_calls}")
    print(f"Cost (@ $0.003/call): ${client.api_calls * 0.003:.3f}\n")


async def demo_with_cache():
    """Demonstrate LLM calls with caching."""
    print("=== With Cache ===\n")

    redis = RedisClient(url="redis://localhost:6379")
    cache = LLMResponseCache(redis=redis, default_ttl=3600)
    client = MockLLMClient(cache=cache)

    content = "Python is a high-level programming language."

    # Multiple calls - only first hits API
    for i in range(3):
        desc = await client.generate_embedding_description(content)
        summary = await client.generate_summary(content)
        print(f"Iteration {i+1}:")
        print(f"  Description: {desc[:60]}...")
        print(f"  Summary: {summary[:60]}...")

    print(f"\nTotal API calls: {client.api_calls}")
    print(f"Cost (@ $0.003/call): ${client.api_calls * 0.003:.3f}")

    # Show cache statistics
    stats = cache.get_stats()
    print(f"\nCache Statistics:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit Rate: {stats['hit_rate']:.2%}")

    # Show savings
    savings = cache.estimate_savings(cost_per_call=0.003)
    print(f"\nEstimated Savings:")
    print(f"  Cache Hits: {savings['cache_hits']}")
    print(f"  Savings: ${savings['estimated_savings_usd']:.3f}")


async def demo_model_specific():
    """Demonstrate model-specific caching."""
    print("\n=== Model-Specific Caching ===\n")

    redis = RedisClient(url="redis://localhost:6379")
    cache = LLMResponseCache(redis=redis)
    client = MockLLMClient(cache=cache)

    content = "Machine learning is a subset of AI."

    # Same prompt, different models - each cached separately
    for model in ["sonnet", "opus", "haiku"]:
        desc = await client.generate_embedding_description(content, model=model)
        print(f"{model.upper()}: {desc[:60]}...")

    print(f"\nAPI calls made: {client.api_calls}")
    print("(3 calls - one per model, each cached)")

    # Subsequent calls hit cache
    print("\nRepeating calls:")
    for model in ["sonnet", "opus", "haiku"]:
        desc = await client.generate_embedding_description(content, model=model)
        print(f"{model.upper()}: {desc[:60]}...")

    print(f"\nTotal API calls: {client.api_calls}")
    print("(Still 3 - all from cache)")


async def demo_cache_invalidation():
    """Demonstrate cache invalidation."""
    print("\n=== Cache Invalidation ===\n")

    redis = RedisClient(url="redis://localhost:6379")
    cache = LLMResponseCache(redis=redis)
    client = MockLLMClient(cache=cache)

    content = "Redis is an in-memory data store."

    # First call - cache miss
    print("1. Initial call (cache miss):")
    desc1 = await client.generate_embedding_description(content)
    print(f"   Response: {desc1[:60]}...")
    print(f"   API calls: {client.api_calls}")

    # Second call - cache hit
    print("\n2. Repeated call (cache hit):")
    desc2 = await client.generate_embedding_description(content)
    print(f"   Response: {desc2[:60]}...")
    print(f"   API calls: {client.api_calls}")

    # Invalidate cache
    print("\n3. Invalidating cache...")
    prompt = f"Describe this content concisely for semantic search:\n\n{content}"
    cache.invalidate(prompt, model="sonnet")

    # Third call - cache miss again
    print("\n4. Call after invalidation (cache miss):")
    desc3 = await client.generate_embedding_description(content)
    print(f"   Response: {desc3[:60]}...")
    print(f"   API calls: {client.api_calls}")


async def main():
    """Run all demonstrations."""
    print("╔════════════════════════════════════════════════╗")
    print("║   LLM Response Cache Integration Demo          ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Demo 1: Compare with and without cache
    await demo_without_cache()
    await demo_with_cache()

    # Demo 2: Model-specific caching
    await demo_model_specific()

    # Demo 3: Cache invalidation
    await demo_cache_invalidation()

    print("\n" + "="*50)
    print("Demo complete!")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
