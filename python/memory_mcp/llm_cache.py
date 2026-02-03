# llm_cache.py
# LLM Response Cache for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Caches LLM responses to reduce API costs and latency.
# Supports exact-match caching (SHA256 hash) and optional semantic
# similarity matching using embeddings.
#
# SECURITY: Uses validated Pydantic models for all cached data.

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from .embedding_cache import UnifiedEmbeddingCache
    from .redis_client import RedisClient

logger = logging.getLogger("memory_mcp.llm_cache")


# ============================================================================
# PYDANTIC MODELS FOR VALIDATION
# ============================================================================


class LLMCacheEntryModel(BaseModel):
    """Validated LLM cache entry from Redis."""

    prompt_hash: str = Field(..., min_length=32, max_length=64)
    prompt: str = Field(..., max_length=100_000)
    response: str = Field(..., max_length=500_000)
    model: str = Field(..., max_length=100)
    created_at: str = Field(...)
    access_count: int = Field(default=1, ge=0, le=1_000_000)

    @field_validator("prompt_hash")
    @classmethod
    def check_prompt_hash(cls, v: str) -> str:
        """Validate prompt hash is hex string."""
        if not v or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Invalid prompt hash format")
        return v.lower()

    @field_validator("prompt")
    @classmethod
    def check_prompt(cls, v: str) -> str:
        """Validate prompt is non-empty."""
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v

    @field_validator("response")
    @classmethod
    def check_response(cls, v: str) -> str:
        """Validate response is non-empty."""
        if not v or not v.strip():
            raise ValueError("Response cannot be empty")
        return v

    @field_validator("model")
    @classmethod
    def check_model(cls, v: str) -> str:
        """Validate model name."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v

    @field_validator("created_at")
    @classmethod
    def check_created_at(cls, v: str) -> str:
        """Validate ISO 8601 timestamp."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid timestamp: {v}") from e

    model_config = ConfigDict(extra="forbid")


# ============================================================================
# STATS TRACKING
# ============================================================================


@dataclass
class LLMCacheStats:
    """Statistics for LLM response cache."""

    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    stores: int = 0
    errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_exact_hit(self) -> None:
        """Record an exact match cache hit."""
        with self._lock:
            self.exact_hits += 1

    def record_semantic_hit(self) -> None:
        """Record a semantic similarity cache hit."""
        with self._lock:
            self.semantic_hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.misses += 1

    def record_store(self) -> None:
        """Record a cache store operation."""
        with self._lock:
            self.stores += 1

    def record_error(self) -> None:
        """Record an error."""
        with self._lock:
            self.errors += 1

    @property
    def total_hits(self) -> int:
        """Total cache hits."""
        return self.exact_hits + self.semantic_hits

    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.total_hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.total_hits / self.total_requests

    def to_dict(self) -> Dict:
        """Convert stats to dictionary."""
        return {
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "total_hits": self.total_hits,
            "misses": self.misses,
            "stores": self.stores,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
        }


# ============================================================================
# LLM RESPONSE CACHE
# ============================================================================


class LLMResponseCache:
    """LLM response cache with exact and semantic matching.

    Provides two-tier caching for LLM responses:
    1. Exact match: SHA256 hash of prompt
    2. Semantic match: Cosine similarity of embeddings (optional)

    Thread-safe for concurrent access.

    Example:
        cache = LLMResponseCache(redis_client, embedding_cache)

        # Get or generate response
        response, was_cached = await cache.get_or_generate(
            prompt="Explain recursion",
            generator=lambda p: call_llm(p),
            model="claude-sonnet-4-5"
        )

        if was_cached:
            print("Cache hit!")
    """

    # Redis key prefix
    PREFIX = "cc:llm:"

    # Default TTL: 1 hour (in seconds)
    DEFAULT_TTL = 3600

    # Semantic similarity threshold (0.95 = very similar)
    DEFAULT_SIMILARITY_THRESHOLD = 0.95

    def __init__(
        self,
        redis: "RedisClient",
        embedding_cache: Optional["UnifiedEmbeddingCache"] = None,
        ttl: int = DEFAULT_TTL,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        enable_semantic: bool = True,
    ):
        """Initialize the LLM response cache.

        Args:
            redis: Redis client for cache storage
            embedding_cache: Optional embedding cache for semantic matching
            ttl: Cache TTL in seconds (default: 1 hour)
            similarity_threshold: Minimum similarity for semantic matches (0.0-1.0)
            enable_semantic: Whether to enable semantic similarity matching
        """
        self.redis = redis
        self.embedding_cache = embedding_cache
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self.enable_semantic = enable_semantic and embedding_cache is not None

        self._lock = threading.Lock()
        self._stats = LLMCacheStats()

        # In-memory index of prompt hashes to embeddings (for semantic search)
        # Maps: prompt_hash -> embedding vector
        self._embedding_index: Dict[str, List[float]] = {}
        self._index_lock = threading.Lock()

    def _cache_key(self, prompt_hash: str) -> str:
        """Generate Redis cache key from prompt hash."""
        return f"{self.PREFIX}{prompt_hash}"

    def _hash_prompt(self, prompt: str) -> str:
        """Generate SHA256 hash of prompt.

        Returns first 32 characters of hex digest for compact storage.
        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]

    def _cosine_similarity(
        self, vec1: List[float], vec2: List[float]
    ) -> float:
        """Calculate cosine similarity between two vectors.

        Returns value between -1.0 and 1.0.
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _get_exact_match(self, prompt_hash: str) -> Optional[str]:
        """Get cached response by exact prompt hash match.

        Returns:
            Cached response string if found, None otherwise
        """
        if not self.redis.is_connected:
            return None

        key = self._cache_key(prompt_hash)

        try:
            data = self.redis._client.get(key)
            if not data:
                return None

            # Parse and validate
            raw_data = json.loads(data)
            validated = LLMCacheEntryModel(**raw_data)

            # Update access count
            updated = {
                **raw_data,
                "access_count": validated.access_count + 1,
            }
            self.redis._client.setex(key, self.ttl, json.dumps(updated))

            self._stats.record_exact_hit()
            logger.debug(f"LLM cache exact hit for hash {prompt_hash[:8]}...")

            return validated.response

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse cached LLM response: {e}")
            self._stats.record_error()
            return None
        except Exception as e:
            logger.warning(f"Error retrieving cached LLM response: {e}")
            self._stats.record_error()
            return None

    def _find_semantic_match(
        self, prompt_embedding: List[float]
    ) -> Optional[str]:
        """Find semantically similar cached response.

        Args:
            prompt_embedding: Embedding vector of the prompt

        Returns:
            Cached response if similar enough, None otherwise
        """
        if not self.enable_semantic:
            return None

        with self._index_lock:
            best_match: Optional[Tuple[str, float]] = None

            for prompt_hash, cached_embedding in self._embedding_index.items():
                similarity = self._cosine_similarity(
                    prompt_embedding, cached_embedding
                )

                if similarity >= self.similarity_threshold:
                    if best_match is None or similarity > best_match[1]:
                        best_match = (prompt_hash, similarity)

            if best_match is None:
                return None

            prompt_hash, similarity = best_match

        # Retrieve the cached response
        response = self._get_exact_match(prompt_hash)

        if response:
            self._stats.record_semantic_hit()
            logger.debug(
                f"LLM cache semantic hit (similarity={similarity:.3f}) "
                f"for hash {prompt_hash[:8]}..."
            )
            return response

        return None

    def _store_response(
        self,
        prompt: str,
        prompt_hash: str,
        response: str,
        model: str,
        embedding: Optional[List[float]] = None,
    ) -> bool:
        """Store response in cache.

        Args:
            prompt: Original prompt text
            prompt_hash: SHA256 hash of prompt
            response: LLM response to cache
            model: Model name used
            embedding: Optional prompt embedding for semantic search

        Returns:
            True if stored successfully
        """
        if not self.redis.is_connected:
            return False

        key = self._cache_key(prompt_hash)
        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "prompt_hash": prompt_hash,
            "prompt": prompt,
            "response": response,
            "model": model,
            "created_at": now,
            "access_count": 1,
        }

        try:
            # Validate before storing
            LLMCacheEntryModel(**entry)

            self.redis._client.setex(key, self.ttl, json.dumps(entry))

            # Store embedding in index for semantic search
            if embedding and self.enable_semantic:
                with self._index_lock:
                    self._embedding_index[prompt_hash] = embedding

            self._stats.record_store()
            logger.debug(f"Cached LLM response for hash {prompt_hash[:8]}...")

            return True

        except Exception as e:
            logger.warning(f"Failed to cache LLM response: {e}")
            self._stats.record_error()
            return False

    async def get_or_generate(
        self,
        prompt: str,
        generator: Callable[[str], Awaitable[str]],
        model: str = "unknown",
    ) -> Tuple[str, bool]:
        """Get cached response or generate new one.

        This is the main entry point for the cache. It first checks for
        an exact match, then optionally checks for semantic similarity,
        and finally generates a new response if no cache hit.

        Args:
            prompt: The prompt to look up or generate response for
            generator: Async function to generate response if not cached
            model: Model name (used for cache metadata)

        Returns:
            Tuple of (response, was_cached)
        """
        # Calculate prompt hash for exact matching
        prompt_hash = self._hash_prompt(prompt)

        # Try exact match first (fastest)
        cached_response = self._get_exact_match(prompt_hash)
        if cached_response:
            return cached_response, True

        # Try semantic match (if enabled and embedding cache available)
        if self.enable_semantic and self.embedding_cache:
            prompt_embedding = self.embedding_cache.get(prompt)

            if prompt_embedding:
                semantic_response = self._find_semantic_match(prompt_embedding)
                if semantic_response:
                    return semantic_response, True

        # Cache miss - generate new response
        self._stats.record_miss()
        logger.debug(f"LLM cache miss for hash {prompt_hash[:8]}...")

        response = await generator(prompt)

        # Get or generate embedding for semantic index
        prompt_embedding = None
        if self.enable_semantic and self.embedding_cache:
            prompt_embedding = self.embedding_cache.get(prompt)
            # Note: We don't generate embeddings here to avoid additional
            # API calls. The embedding should already exist if the user
            # has used the embedding cache for this prompt.

        # Store in cache
        self._store_response(
            prompt=prompt,
            prompt_hash=prompt_hash,
            response=response,
            model=model,
            embedding=prompt_embedding,
        )

        return response, False

    def get(self, prompt: str) -> Optional[str]:
        """Get cached response by prompt (exact match only).

        This is a synchronous method for simple cache lookups without
        generation.

        Args:
            prompt: The prompt to look up

        Returns:
            Cached response if found, None otherwise
        """
        prompt_hash = self._hash_prompt(prompt)
        return self._get_exact_match(prompt_hash)

    def invalidate(self, prompt: str) -> bool:
        """Invalidate cached response for a prompt.

        Args:
            prompt: The prompt to invalidate

        Returns:
            True if entry was deleted
        """
        if not self.redis.is_connected:
            return False

        prompt_hash = self._hash_prompt(prompt)
        key = self._cache_key(prompt_hash)

        try:
            deleted = self.redis._client.delete(key) > 0

            # Remove from semantic index
            with self._index_lock:
                self._embedding_index.pop(prompt_hash, None)

            if deleted:
                logger.debug(f"Invalidated LLM cache for hash {prompt_hash[:8]}...")

            return deleted

        except Exception as e:
            logger.warning(f"Failed to invalidate LLM cache: {e}")
            self._stats.record_error()
            return False

    def clear(self) -> int:
        """Clear all cached LLM responses.

        Returns:
            Number of entries cleared
        """
        if not self.redis.is_connected:
            return 0

        cleared = 0
        pattern = f"{self.PREFIX}*"

        try:
            # Use SCAN for non-blocking iteration
            cursor = 0
            while True:
                cursor, keys = self.redis._client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    cleared += self.redis._client.delete(*keys)
                if cursor == 0:
                    break

            # Clear semantic index
            with self._index_lock:
                self._embedding_index.clear()

            logger.info(f"Cleared {cleared} LLM cache entries")

        except Exception as e:
            logger.warning(f"Failed to clear LLM cache: {e}")
            self._stats.record_error()

        return cleared

    def get_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats including hit rates and counts
        """
        stats = self._stats.to_dict()

        # Add cache size info
        if self.redis.is_connected:
            try:
                pattern = f"{self.PREFIX}*"
                cursor = 0
                count = 0

                while True:
                    cursor, keys = self.redis._client.scan(
                        cursor=cursor, match=pattern, count=100
                    )
                    count += len(keys)
                    if cursor == 0:
                        break

                stats["cache_size"] = count
            except Exception:
                stats["cache_size"] = -1
        else:
            stats["cache_size"] = 0

        # Add semantic index size
        with self._index_lock:
            stats["semantic_index_size"] = len(self._embedding_index)

        stats["ttl_seconds"] = self.ttl
        stats["similarity_threshold"] = self.similarity_threshold
        stats["semantic_enabled"] = self.enable_semantic

        return stats

    def health_check(self) -> bool:
        """Check if cache is healthy.

        Returns:
            True if Redis is connected and responding
        """
        return self.redis.is_connected
