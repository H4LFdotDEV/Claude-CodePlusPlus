"""Tests for LLM response caching."""

import json
import time
from unittest.mock import MagicMock, Mock

import pytest

from shared.llm_cache import LLMResponseCache


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = MagicMock()
    redis.connected = True
    redis._cache = {}  # Simple in-memory store for testing

    def get(key):
        return redis._cache.get(key)

    def setex(key, ttl, value):
        redis._cache[key] = value
        return True

    def delete(*keys):
        count = 0
        for key in keys:
            if key in redis._cache:
                del redis._cache[key]
                count += 1
        return count

    def scan_iter(match=None):
        if match:
            pattern = match.replace('*', '')
            return [k for k in redis._cache.keys() if k.startswith(pattern)]
        return list(redis._cache.keys())

    redis.get = get
    redis.setex = setex
    redis.delete = delete
    redis.scan_iter = scan_iter

    return redis


@pytest.fixture
def cache(mock_redis):
    """LLM cache with mock Redis."""
    return LLMResponseCache(redis=mock_redis, default_ttl=3600)


@pytest.fixture
def cache_no_redis():
    """LLM cache without Redis backend."""
    return LLMResponseCache(redis=None)


def test_cache_initialization(cache):
    """Test cache initializes with correct defaults."""
    assert cache.default_ttl == 3600
    assert cache._stats == {"hits": 0, "misses": 0, "stores": 0}
    assert cache.redis is not None


def test_hash_prompt_consistency(cache):
    """Test prompt hashing is consistent."""
    prompt = "What is the capital of France?"
    hash1 = cache._hash_prompt(prompt)
    hash2 = cache._hash_prompt(prompt)
    assert hash1 == hash2
    assert len(hash1) == 32  # First 32 chars of SHA256


def test_hash_prompt_uniqueness(cache):
    """Test different prompts produce different hashes."""
    hash1 = cache._hash_prompt("prompt 1")
    hash2 = cache._hash_prompt("prompt 2")
    assert hash1 != hash2


def test_cache_key_format(cache):
    """Test cache key generation format."""
    key = cache._cache_key("abc123", "sonnet")
    assert key == "cc:llm:sonnet:abc123"


def test_set_and_get_cache_hit(cache):
    """Test storing and retrieving cached response."""
    prompt = "What is 2+2?"
    response = "4"
    model = "sonnet"

    # Store in cache
    cache.set(prompt, response, model)

    # Retrieve from cache
    cached = cache.get(prompt, model)
    assert cached == response
    assert cache._stats["stores"] == 1
    assert cache._stats["hits"] == 1
    assert cache._stats["misses"] == 0


def test_get_cache_miss(cache):
    """Test cache miss returns None."""
    prompt = "This prompt was never cached"
    result = cache.get(prompt)

    assert result is None
    assert cache._stats["misses"] == 1
    assert cache._stats["hits"] == 0


def test_cache_miss_without_redis(cache_no_redis):
    """Test cache always misses without Redis."""
    cache_no_redis.set("prompt", "response")
    result = cache_no_redis.get("prompt")

    assert result is None
    assert cache_no_redis._stats["misses"] == 1


def test_model_specific_caching(cache):
    """Test same prompt cached separately per model."""
    prompt = "Explain quantum computing"
    response_sonnet = "Sonnet response"
    response_opus = "Opus response"

    # Store for different models
    cache.set(prompt, response_sonnet, "sonnet")
    cache.set(prompt, response_opus, "opus")

    # Retrieve model-specific responses
    assert cache.get(prompt, "sonnet") == response_sonnet
    assert cache.get(prompt, "opus") == response_opus


def test_hit_count_increments(cache):
    """Test hit count increments on repeated access."""
    prompt = "Test prompt"
    response = "Test response"

    cache.set(prompt, response)

    # Access multiple times
    for _ in range(5):
        cache.get(prompt)

    # Check stored entry
    prompt_hash = cache._hash_prompt(prompt)
    key = cache._cache_key(prompt_hash, "sonnet")
    entry = json.loads(cache.redis.get(key))

    assert entry["hit_count"] == 5


def test_custom_ttl(cache):
    """Test custom TTL is stored in entry."""
    prompt = "Custom TTL test"
    response = "Response"
    custom_ttl = 7200

    cache.set(prompt, response, ttl=custom_ttl)

    # Verify TTL in stored entry
    prompt_hash = cache._hash_prompt(prompt)
    key = cache._cache_key(prompt_hash, "sonnet")
    entry = json.loads(cache.redis.get(key))

    assert entry["ttl"] == custom_ttl


def test_invalidate_cached_entry(cache):
    """Test invalidating a cached entry."""
    prompt = "To be invalidated"
    response = "Cached response"

    # Store and verify
    cache.set(prompt, response)
    assert cache.get(prompt) is not None

    # Invalidate
    result = cache.invalidate(prompt)
    assert result is True

    # Verify removed
    assert cache.get(prompt) is None


def test_invalidate_nonexistent_entry(cache):
    """Test invalidating non-existent entry."""
    result = cache.invalidate("never existed")
    assert result is False


def test_clear_model(cache):
    """Test clearing all entries for a model."""
    # Store multiple entries for different models
    cache.set("prompt1", "response1", "sonnet")
    cache.set("prompt2", "response2", "sonnet")
    cache.set("prompt3", "response3", "opus")

    # Clear sonnet model
    count = cache.clear_model("sonnet")

    assert count == 2
    assert cache.get("prompt1", "sonnet") is None
    assert cache.get("prompt2", "sonnet") is None
    assert cache.get("prompt3", "opus") is not None


def test_get_stats_empty_cache(cache):
    """Test statistics for empty cache."""
    stats = cache.get_stats()

    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["stores"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["redis_available"] is True


def test_get_stats_with_activity(cache):
    """Test statistics after cache activity."""
    # Generate some activity
    cache.set("prompt1", "response1")
    cache.set("prompt2", "response2")
    cache.get("prompt1")  # hit
    cache.get("prompt1")  # hit
    cache.get("prompt3")  # miss

    stats = cache.get_stats()

    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["stores"] == 2
    assert stats["hit_rate"] == 0.6667  # 2/3


def test_estimate_savings_no_hits(cache):
    """Test savings estimation with no cache hits."""
    savings = cache.estimate_savings()

    assert savings["cache_hits"] == 0
    assert savings["estimated_savings_usd"] == 0.0
    assert savings["cost_per_call_usd"] == 0.003


def test_estimate_savings_with_hits(cache):
    """Test savings estimation with cache hits."""
    # Generate 10 cache hits
    cache.set("prompt", "response")
    for _ in range(10):
        cache.get("prompt")

    savings = cache.estimate_savings(cost_per_call=0.005)

    assert savings["cache_hits"] == 10
    assert savings["estimated_savings_usd"] == 0.05  # 10 * 0.005
    assert savings["cost_per_call_usd"] == 0.005


@pytest.mark.asyncio
async def test_get_or_generate_cache_hit(cache):
    """Test get_or_generate returns cached value."""
    prompt = "Test prompt"
    cached_response = "Cached response"

    # Pre-populate cache
    cache.set(prompt, cached_response)

    # Generator should not be called
    async def generator(p):
        raise AssertionError("Generator should not be called on cache hit")

    response, was_cached = await cache.get_or_generate(prompt, generator)

    assert response == cached_response
    assert was_cached is True


@pytest.mark.asyncio
async def test_get_or_generate_cache_miss(cache):
    """Test get_or_generate generates and caches on miss."""
    prompt = "New prompt"
    generated_response = "Generated response"

    # Generator returns new response
    async def generator(p):
        return generated_response

    response, was_cached = await cache.get_or_generate(prompt, generator)

    assert response == generated_response
    assert was_cached is False

    # Verify it was cached
    assert cache.get(prompt) == generated_response


@pytest.mark.asyncio
async def test_get_or_generate_custom_ttl(cache):
    """Test get_or_generate with custom TTL."""
    prompt = "Custom TTL"
    response = "Response"
    custom_ttl = 1800

    async def generator(p):
        return response

    await cache.get_or_generate(prompt, generator, ttl=custom_ttl)

    # Verify TTL in cache
    prompt_hash = cache._hash_prompt(prompt)
    key = cache._cache_key(prompt_hash, "sonnet")
    entry = json.loads(cache.redis.get(key))

    assert entry["ttl"] == custom_ttl


def test_cache_entry_structure(cache):
    """Test cached entry has correct structure."""
    prompt = "Structure test"
    response = "Test response"
    model = "sonnet"

    cache.set(prompt, response, model)

    # Get raw entry from Redis
    prompt_hash = cache._hash_prompt(prompt)
    key = cache._cache_key(prompt_hash, model)
    entry = json.loads(cache.redis.get(key))

    assert "prompt_hash" in entry
    assert "response" in entry
    assert "model" in entry
    assert "created_at" in entry
    assert "ttl" in entry
    assert "hit_count" in entry

    assert entry["response"] == response
    assert entry["model"] == model


def test_redis_connection_failure_handling(cache):
    """Test graceful handling when Redis fails."""
    # Simulate Redis connection failure
    cache.redis.connected = False

    # These should not raise exceptions
    cache.set("prompt", "response")
    result = cache.get("prompt")

    assert result is None
    assert cache._stats["misses"] == 1


def test_redis_exception_handling(cache):
    """Test graceful handling of Redis exceptions."""
    # Make Redis operations raise exceptions
    cache.redis.get = Mock(side_effect=Exception("Redis error"))
    cache.redis.setex = Mock(side_effect=Exception("Redis error"))

    # Should handle exceptions gracefully
    cache.set("prompt", "response")
    result = cache.get("prompt")

    assert result is None
    assert cache._stats["misses"] == 1


def test_cache_multiple_prompts(cache):
    """Test caching multiple different prompts."""
    prompts_responses = [
        ("What is AI?", "Artificial Intelligence explanation"),
        ("How does ML work?", "Machine Learning explanation"),
        ("Explain neural networks", "Neural network explanation"),
    ]

    # Cache all prompts
    for prompt, response in prompts_responses:
        cache.set(prompt, response)

    # Verify all are cached
    for prompt, expected_response in prompts_responses:
        assert cache.get(prompt) == expected_response

    assert cache._stats["stores"] == 3
    assert cache._stats["hits"] == 3


def test_stats_without_redis(cache_no_redis):
    """Test stats when Redis is not available."""
    stats = cache_no_redis.get_stats()

    assert stats["redis_available"] is False
    assert stats["hits"] == 0
    assert stats["misses"] == 0


def test_session_isolation_initialization(mock_redis):
    """Test cache initializes with session_id."""
    session_id = "session-123"
    cache = LLMResponseCache(redis=mock_redis, session_id=session_id)

    assert cache.session_id == session_id


def test_session_isolation_cache_key_format(mock_redis):
    """Test cache key includes session_id when set."""
    session_id = "session-456"
    cache = LLMResponseCache(redis=mock_redis, session_id=session_id)

    key = cache._cache_key("abc123", "sonnet")
    assert key == "cc:llm:sonnet:session-456:abc123"


def test_session_isolation_no_session_cache_key(cache):
    """Test cache key without session_id maintains backward compatibility."""
    key = cache._cache_key("abc123", "sonnet")
    assert key == "cc:llm:sonnet:abc123"


def test_session_isolation_prevents_cross_session_access(mock_redis):
    """Test sessions cannot access each other's cache."""
    prompt = "What is 2+2?"
    response_session1 = "4 (from session 1)"
    response_session2 = "4 (from session 2)"

    # Create two caches with different session IDs
    cache_session1 = LLMResponseCache(redis=mock_redis, session_id="session-1")
    cache_session2 = LLMResponseCache(redis=mock_redis, session_id="session-2")

    # Store in session 1
    cache_session1.set(prompt, response_session1)

    # Store in session 2
    cache_session2.set(prompt, response_session2)

    # Verify isolation - each session gets its own response
    assert cache_session1.get(prompt) == response_session1
    assert cache_session2.get(prompt) == response_session2


def test_session_isolation_prevents_cache_poisoning(mock_redis):
    """Test malicious session cannot poison another session's cache."""
    prompt = "Execute command"
    malicious_response = "Malicious content"
    legitimate_response = "Legitimate content"

    # Malicious session
    cache_malicious = LLMResponseCache(redis=mock_redis, session_id="malicious-session")
    cache_malicious.set(prompt, malicious_response)

    # Legitimate session
    cache_legitimate = LLMResponseCache(redis=mock_redis, session_id="legitimate-session")
    cache_legitimate.set(prompt, legitimate_response)

    # Verify legitimate session is not affected
    assert cache_legitimate.get(prompt) == legitimate_response
    assert cache_legitimate.get(prompt) != malicious_response


def test_global_cache_without_session_id(mock_redis):
    """Test global cache behavior without session_id."""
    prompt = "Global prompt"
    response = "Global response"

    # Two caches without session_id should share cache
    cache1 = LLMResponseCache(redis=mock_redis)
    cache2 = LLMResponseCache(redis=mock_redis)

    # Store in cache1
    cache1.set(prompt, response)

    # Retrieve from cache2
    assert cache2.get(prompt) == response


def test_session_isolation_invalidate(mock_redis):
    """Test invalidate only affects current session."""
    prompt = "Test prompt"

    cache_session1 = LLMResponseCache(redis=mock_redis, session_id="session-1")
    cache_session2 = LLMResponseCache(redis=mock_redis, session_id="session-2")

    # Store in both sessions
    cache_session1.set(prompt, "Response 1")
    cache_session2.set(prompt, "Response 2")

    # Invalidate in session 1
    result = cache_session1.invalidate(prompt)
    assert result is True

    # Verify session 1 is invalidated but session 2 is not
    assert cache_session1.get(prompt) is None
    assert cache_session2.get(prompt) == "Response 2"


def test_set_session_id_changes_isolation(mock_redis):
    """Test set_session_id changes cache isolation."""
    prompt = "Dynamic session test"
    cache = LLMResponseCache(redis=mock_redis)

    # Store in global cache
    cache.set(prompt, "Global response")
    assert cache.get(prompt) == "Global response"

    # Switch to session-specific cache
    cache.set_session_id("new-session")
    assert cache.get(prompt) is None  # Different cache namespace

    # Store in session cache
    cache.set(prompt, "Session response")
    assert cache.get(prompt) == "Session response"

    # Switch back to global
    cache.set_session_id(None)
    assert cache.get(prompt) == "Global response"


def test_session_isolation_clear_model(mock_redis):
    """Test clear_model respects session isolation."""
    cache_session1 = LLMResponseCache(redis=mock_redis, session_id="session-1")
    cache_session2 = LLMResponseCache(redis=mock_redis, session_id="session-2")

    # Store entries in both sessions
    cache_session1.set("prompt1", "response1", "sonnet")
    cache_session1.set("prompt2", "response2", "sonnet")
    cache_session2.set("prompt1", "response1", "sonnet")

    # Clear model in session 1
    count = cache_session1.clear_model("sonnet")

    # Should only clear session 1's entries
    assert count == 2
    assert cache_session1.get("prompt1", "sonnet") is None
    assert cache_session2.get("prompt1", "sonnet") is not None


@pytest.mark.asyncio
async def test_session_isolation_get_or_generate(mock_redis):
    """Test get_or_generate respects session isolation."""
    prompt = "Generate test"
    response1 = "Session 1 response"
    response2 = "Session 2 response"

    cache_session1 = LLMResponseCache(redis=mock_redis, session_id="session-1")
    cache_session2 = LLMResponseCache(redis=mock_redis, session_id="session-2")

    # Generate for session 1
    async def generator1(p):
        return response1

    result1, cached1 = await cache_session1.get_or_generate(prompt, generator1)
    assert result1 == response1
    assert cached1 is False

    # Generate for session 2 (should not use session 1's cache)
    async def generator2(p):
        return response2

    result2, cached2 = await cache_session2.get_or_generate(prompt, generator2)
    assert result2 == response2
    assert cached2 is False

    # Verify both sessions have their own cached values
    assert cache_session1.get(prompt) == response1
    assert cache_session2.get(prompt) == response2
