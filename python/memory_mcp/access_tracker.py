# access_tracker.py
# Tracks document access patterns for tier promotion decisions
# Jeremiah Kroesche | Halfservers LLC

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .redis_client import RedisClient

# Maximum entries in local cache before LRU eviction
MAX_LOCAL_CACHE_SIZE = 10000


@dataclass
class AccessStats:
    """Statistics for a single document's access patterns."""

    doc_id: str
    access_count: int = 0
    last_access: Optional[datetime] = None
    content_size: int = 0
    first_access: Optional[datetime] = None

    def record_access(self, size: int = 0) -> None:
        """Record an access to this document."""
        now = datetime.now(timezone.utc)
        self.access_count += 1
        self.last_access = now
        if self.first_access is None:
            self.first_access = now
        if size > 0:
            self.content_size = size


class AccessTracker:
    """Tracks document access patterns for promotion decisions.

    Uses Redis for distributed tracking when available,
    falls back to local in-memory cache with LRU eviction.
    """

    def __init__(
        self,
        redis_client: Optional["RedisClient"] = None,
        max_cache_size: int = MAX_LOCAL_CACHE_SIZE
    ):
        self.redis = redis_client
        self._max_cache_size = max_cache_size
        # OrderedDict for LRU eviction (most recently used at end)
        self._local_cache: OrderedDict[str, AccessStats] = OrderedDict()

    def record_access(self, doc_id: str, size: int = 0) -> None:
        """Record an access to a document."""
        key = f"access:{doc_id}"

        if self.redis:
            try:
                pipe = self.redis._client.pipeline() if hasattr(self.redis, '_client') else None
                if pipe:
                    pipe.hincrby(key, "count", 1)
                    pipe.hset(key, "last_access", datetime.now(timezone.utc).isoformat())
                    if size > 0:
                        pipe.hset(key, "content_size", size)
                    pipe.expire(key, 86400)  # 24h TTL
                    pipe.execute()
                    return
            except Exception:
                pass  # Fall back to local cache

        # Local cache fallback with LRU eviction
        if doc_id in self._local_cache:
            # Move to end (most recently used)
            self._local_cache.move_to_end(doc_id)
        else:
            # Evict oldest entries if cache is full
            while len(self._local_cache) >= self._max_cache_size:
                self._local_cache.popitem(last=False)  # Remove oldest (first)
            self._local_cache[doc_id] = AccessStats(doc_id=doc_id)
        self._local_cache[doc_id].record_access(size)

    def get_stats(self, doc_id: str) -> AccessStats:
        """Get access statistics for a document."""
        key = f"access:{doc_id}"

        if self.redis:
            try:
                if hasattr(self.redis, '_client') and self.redis._client:
                    data = self.redis._client.hgetall(key)
                    if data:
                        return AccessStats(
                            doc_id=doc_id,
                            access_count=int(data.get(b"count", data.get("count", 0))),
                            last_access=datetime.fromisoformat(
                                data.get(b"last_access", data.get("last_access", "")).decode()
                                if isinstance(data.get(b"last_access", data.get("last_access", "")), bytes)
                                else data.get(b"last_access", data.get("last_access", ""))
                            ) if data.get(b"last_access", data.get("last_access")) else None,
                            content_size=int(data.get(b"content_size", data.get("content_size", 0)))
                        )
            except Exception:
                pass  # Fall back to local cache

        # Local cache fallback
        if doc_id in self._local_cache:
            # Move to end (most recently accessed)
            self._local_cache.move_to_end(doc_id)
            return self._local_cache[doc_id]
        return AccessStats(doc_id=doc_id)

    def get_hot_documents(self, threshold: int = 5, limit: int = 100) -> list:
        """Get documents that have been accessed frequently.

        Args:
            threshold: Minimum access count to be considered "hot"
            limit: Maximum documents to return

        Returns:
            List of (doc_id, access_count) tuples, sorted by access count descending
        """
        hot_docs = []

        # Check local cache
        for doc_id, stats in self._local_cache.items():
            if stats.access_count >= threshold:
                hot_docs.append((doc_id, stats.access_count))

        # Sort by access count descending and limit
        hot_docs.sort(key=lambda x: x[1], reverse=True)
        return hot_docs[:limit]

    def clear_stats(self, doc_id: str) -> None:
        """Clear access statistics for a document."""
        if doc_id in self._local_cache:
            del self._local_cache[doc_id]

        if self.redis:
            try:
                if hasattr(self.redis, '_client') and self.redis._client:
                    self.redis._client.delete(f"access:{doc_id}")
            except Exception:
                pass

    def reset(self) -> None:
        """Reset all access statistics."""
        self._local_cache.clear()
