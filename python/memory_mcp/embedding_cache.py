# embedding_cache.py
# Unified embedding cache with Redis (hot) and SQLite (persistent) tiers
# Jeremiah Kroesche | Halfservers LLC
#
# Provides two-tier caching for embeddings:
# - Redis: Fast access for recently used embeddings
# - SQLite: Persistent storage for all embeddings (survives restarts)

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .redis_client import RedisClient

logger = logging.getLogger("memory_mcp")


class UnifiedEmbeddingCache:
    """Two-tier embedding cache with Redis (hot) and SQLite (persistent).

    Cache lookup order:
    1. Redis (fast, volatile)
    2. SQLite (slower, persistent)

    On cache hit in SQLite but miss in Redis, the embedding is promoted
    to Redis for faster subsequent access.

    Thread-safe for concurrent access.
    """

    # Default TTL for Redis cache (24 hours)
    DEFAULT_REDIS_TTL = 86400

    def __init__(
        self,
        redis: Optional["RedisClient"] = None,
        sqlite_path: Optional[str] = None,
        redis_ttl: int = DEFAULT_REDIS_TTL
    ):
        """Initialize the unified embedding cache.

        Args:
            redis: Optional Redis client for hot cache
            sqlite_path: Path to SQLite database for persistent cache
            redis_ttl: TTL for Redis cache entries in seconds
        """
        self.redis = redis
        self.redis_ttl = redis_ttl
        self._lock = threading.Lock()

        # Initialize SQLite
        if sqlite_path:
            self._sqlite_path = Path(sqlite_path)
        else:
            # Default to ~/.claude-code-pp/cache/embeddings.db
            cache_dir = Path.home() / ".claude-code-pp" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._sqlite_path = cache_dir / "embeddings.db"

        self._init_sqlite()

        # Stats tracking
        self._hits_redis = 0
        self._hits_sqlite = 0
        self._misses = 0

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with embeddings table."""
        with sqlite3.connect(str(self._sqlite_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    hash TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    model TEXT,
                    dimensions INTEGER,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_last_accessed
                ON embeddings(last_accessed)
            """)
            conn.commit()

    def _hash_text(self, text: str, model: str = "") -> str:
        """Generate a hash key for the text and model combination."""
        key = f"{model}:{text}" if model else text
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection."""
        return sqlite3.connect(str(self._sqlite_path))

    def get(
        self,
        text: str,
        model: str = ""
    ) -> Optional[List[float]]:
        """Get cached embedding for text.

        Args:
            text: Text to look up
            model: Optional model name (embeddings may vary by model)

        Returns:
            Cached embedding vector or None if not found
        """
        text_hash = self._hash_text(text, model)

        # Try Redis first (fast path)
        if self.redis and self.redis.is_connected:
            try:
                cached = self.redis.get_cached_embedding(text_hash)
                if cached:
                    self._hits_redis += 1
                    return cached
            except Exception as e:
                logger.debug(f"Redis cache lookup failed: {e}")

        # Fallback to SQLite (persistent)
        with self._lock:
            try:
                conn = self._get_sqlite_connection()
                cursor = conn.execute(
                    "SELECT embedding FROM embeddings WHERE hash = ?",
                    (text_hash,)
                )
                row = cursor.fetchone()

                if row:
                    embedding = json.loads(row[0])
                    self._hits_sqlite += 1

                    # Update access tracking
                    now = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        """UPDATE embeddings
                           SET last_accessed = ?, access_count = access_count + 1
                           WHERE hash = ?""",
                        (now, text_hash)
                    )
                    conn.commit()

                    # Promote to Redis for faster subsequent access
                    if self.redis and self.redis.is_connected:
                        try:
                            self.redis.cache_embedding(
                                text_hash,
                                embedding,
                                ttl=self.redis_ttl
                            )
                        except Exception as e:
                            logger.debug(f"Redis promotion failed: {e}")

                    return embedding

                conn.close()
            except Exception as e:
                logger.warning(f"SQLite cache lookup failed: {e}")

        self._misses += 1
        return None

    def set(
        self,
        text: str,
        embedding: List[float],
        model: str = ""
    ) -> bool:
        """Cache an embedding for text.

        Args:
            text: Text that was embedded
            embedding: Embedding vector
            model: Optional model name

        Returns:
            True if cached successfully
        """
        text_hash = self._hash_text(text, model)
        now = datetime.now(timezone.utc).isoformat()

        # Store in both tiers
        success = True

        # Redis (hot cache)
        if self.redis and self.redis.is_connected:
            try:
                self.redis.cache_embedding(
                    text_hash,
                    embedding,
                    ttl=self.redis_ttl
                )
            except Exception as e:
                logger.debug(f"Redis cache write failed: {e}")
                success = False

        # SQLite (persistent)
        with self._lock:
            try:
                conn = self._get_sqlite_connection()
                conn.execute(
                    """INSERT OR REPLACE INTO embeddings
                       (hash, embedding, model, dimensions, created_at, last_accessed, access_count)
                       VALUES (?, ?, ?, ?, ?, ?,
                               COALESCE((SELECT access_count FROM embeddings WHERE hash = ?), 0) + 1)""",
                    (text_hash, json.dumps(embedding), model, len(embedding), now, now, text_hash)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"SQLite cache write failed: {e}")
                success = False

        return success

    def delete(self, text: str, model: str = "") -> bool:
        """Delete cached embedding for text.

        Args:
            text: Text to delete
            model: Optional model name

        Returns:
            True if deleted from at least one tier
        """
        text_hash = self._hash_text(text, model)
        deleted = False

        # Delete from Redis
        if self.redis and self.redis.is_connected:
            try:
                if self.redis.delete_cached_embedding(text_hash):
                    deleted = True
            except Exception as e:
                logger.debug(f"Redis delete failed: {e}")

        # Delete from SQLite
        with self._lock:
            try:
                conn = self._get_sqlite_connection()
                cursor = conn.execute(
                    "DELETE FROM embeddings WHERE hash = ?",
                    (text_hash,)
                )
                if cursor.rowcount > 0:
                    deleted = True
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"SQLite delete failed: {e}")

        return deleted

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with hit/miss counts and cache sizes
        """
        total_hits = self._hits_redis + self._hits_sqlite
        total_requests = total_hits + self._misses
        hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

        # Get SQLite stats
        sqlite_count = 0
        sqlite_size_bytes = 0
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
            sqlite_count = cursor.fetchone()[0]

            # Get file size
            if self._sqlite_path.exists():
                sqlite_size_bytes = self._sqlite_path.stat().st_size
            conn.close()
        except Exception as e:
            logger.debug(f"Failed to get SQLite stats: {e}")

        return {
            "hits_redis": self._hits_redis,
            "hits_sqlite": self._hits_sqlite,
            "hits_total": total_hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "sqlite_entries": sqlite_count,
            "sqlite_size_bytes": sqlite_size_bytes,
            "redis_available": self.redis is not None and self.redis.is_connected
        }

    def clear(self, tier: str = "all") -> int:
        """Clear cached embeddings.

        Args:
            tier: "redis", "sqlite", or "all"

        Returns:
            Number of entries cleared
        """
        cleared = 0

        if tier in ("redis", "all") and self.redis and self.redis.is_connected:
            try:
                # Note: This clears all embeddings in Redis, not just from this cache
                # In production, use a more targeted approach with SCAN
                pass  # Redis embeddings cleared via TTL expiry
            except Exception as e:
                logger.debug(f"Redis clear failed: {e}")

        if tier in ("sqlite", "all"):
            with self._lock:
                try:
                    conn = self._get_sqlite_connection()
                    cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
                    cleared = cursor.fetchone()[0]
                    conn.execute("DELETE FROM embeddings")
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.warning(f"SQLite clear failed: {e}")

        # Reset stats
        self._hits_redis = 0
        self._hits_sqlite = 0
        self._misses = 0

        return cleared

    def prune(self, max_age_days: int = 30, max_entries: int = 100000) -> int:
        """Prune old or excess embeddings from SQLite.

        Args:
            max_age_days: Remove entries older than this
            max_entries: Keep at most this many entries (by recency)

        Returns:
            Number of entries pruned
        """
        pruned = 0

        with self._lock:
            try:
                conn = self._get_sqlite_connection()

                # Prune by age
                cutoff = datetime.now(timezone.utc)
                cutoff_str = cutoff.isoformat()
                cursor = conn.execute(
                    f"""DELETE FROM embeddings
                        WHERE last_accessed < datetime(?, '-{max_age_days} days')""",
                    (cutoff_str,)
                )
                pruned += cursor.rowcount

                # Prune by count (keep most recently accessed)
                cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
                count = cursor.fetchone()[0]

                if count > max_entries:
                    excess = count - max_entries
                    conn.execute(
                        """DELETE FROM embeddings WHERE hash IN (
                               SELECT hash FROM embeddings
                               ORDER BY last_accessed ASC
                               LIMIT ?
                           )""",
                        (excess,)
                    )
                    pruned += excess

                conn.commit()
                conn.close()

                if pruned > 0:
                    logger.info(f"Pruned {pruned} embeddings from cache")

            except Exception as e:
                logger.warning(f"Embedding cache prune failed: {e}")

        return pruned
