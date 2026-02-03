"""LLM Response Caching with Redis backend."""

import hashlib
import json
import time
from typing import Awaitable, Callable, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.redis_client import RedisClient


class LLMResponseCache:
    """Cache for LLM API responses to reduce costs."""

    PREFIX = "cc:llm:"
    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        redis: Optional["RedisClient"] = None,
        default_ttl: int = DEFAULT_TTL,
        session_id: Optional[str] = None
    ):
        self.redis = redis
        self.default_ttl = default_ttl
        self.session_id = session_id
        self._stats: Dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "stores": 0,
        }

    def _cache_key(self, prompt_hash: str, model: str) -> str:
        """Generate cache key for prompt+model combination.

        Includes session_id if set for session isolation.
        """
        if self.session_id:
            return f"{self.PREFIX}{model}:{self.session_id}:{prompt_hash}"
        return f"{self.PREFIX}{model}:{prompt_hash}"

    def _hash_prompt(self, prompt: str) -> str:
        """Generate hash for prompt content."""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:32]

    def get(self, prompt: str, model: str = "sonnet") -> Optional[str]:
        """Get cached response for prompt."""
        if not self.redis or not self.redis.connected:
            self._stats["misses"] += 1
            return None

        prompt_hash = self._hash_prompt(prompt)
        key = self._cache_key(prompt_hash, model)

        try:
            cached = self.redis.get(key)
            if cached:
                entry = json.loads(cached)
                self._stats["hits"] += 1
                # Update hit count in Redis
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                self.redis.setex(key, self.default_ttl, json.dumps(entry))
                return entry["response"]
        except Exception:
            pass

        self._stats["misses"] += 1
        return None

    def set(
        self,
        prompt: str,
        response: str,
        model: str = "sonnet",
        ttl: Optional[int] = None
    ) -> None:
        """Store response in cache."""
        if not self.redis or not self.redis.connected:
            return

        prompt_hash = self._hash_prompt(prompt)
        key = self._cache_key(prompt_hash, model)
        ttl = ttl or self.default_ttl

        entry = {
            "prompt_hash": prompt_hash,
            "response": response,
            "model": model,
            "created_at": time.time(),
            "ttl": ttl,
            "hit_count": 0,
        }

        try:
            self.redis.setex(key, ttl, json.dumps(entry))
            self._stats["stores"] += 1
        except Exception:
            pass

    async def get_or_generate(
        self,
        prompt: str,
        generator: Callable[[str], Awaitable[str]],
        model: str = "sonnet",
        ttl: Optional[int] = None
    ) -> Tuple[str, bool]:
        """Get from cache or generate new response.

        Returns:
            Tuple of (response, was_cached)
        """
        # Check cache first
        cached = self.get(prompt, model)
        if cached is not None:
            return cached, True

        # Generate new response
        response = await generator(prompt)

        # Cache the result
        self.set(prompt, response, model, ttl)

        return response, False

    def invalidate(self, prompt: str, model: str = "sonnet") -> bool:
        """Invalidate a cached entry."""
        if not self.redis or not self.redis.connected:
            return False

        prompt_hash = self._hash_prompt(prompt)
        key = self._cache_key(prompt_hash, model)

        try:
            return self.redis.delete(key) > 0
        except Exception:
            return False

    def clear_model(self, model: str) -> int:
        """Clear all cached entries for a model.

        Respects session isolation - only clears entries for current session.
        """
        if not self.redis or not self.redis.connected:
            return 0

        if self.session_id:
            pattern = f"{self.PREFIX}{model}:{self.session_id}:*"
        else:
            pattern = f"{self.PREFIX}{model}:*"
        count = 0

        try:
            keys = list(self.redis.scan_iter(match=pattern))
            if keys:
                count = self.redis.delete(*keys)
        except Exception:
            pass

        return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "stores": self._stats["stores"],
            "hit_rate": round(hit_rate, 4),
            "redis_available": bool(self.redis and self.redis.connected),
        }

    def estimate_savings(self, cost_per_call: float = 0.003) -> dict:
        """Estimate cost savings from cache hits."""
        hits = self._stats["hits"]
        return {
            "cache_hits": hits,
            "estimated_savings_usd": round(hits * cost_per_call, 4),
            "cost_per_call_usd": cost_per_call,
        }

    def set_session_id(self, session_id: Optional[str]) -> None:
        """Update session_id for cache isolation.

        Args:
            session_id: Session identifier for cache isolation, or None for global cache.
        """
        self.session_id = session_id
