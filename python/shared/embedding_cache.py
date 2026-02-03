"""Unified Embedding Cache with Redis + SQLite fallback."""

import hashlib
import json
import sqlite3
import threading
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.redis_client import RedisClient


class UnifiedEmbeddingCache:
    """Two-tier embedding cache: Redis (hot) + SQLite (persistent)."""

    def __init__(
        self,
        redis: Optional["RedisClient"],
        sqlite_path: str = "~/.claude-code-pp/memory/embeddings.db"
    ):
        import os
        self.redis = redis
        sqlite_path = os.path.expanduser(sqlite_path)
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        self._sqlite_path = sqlite_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self._sqlite_path,
                check_same_thread=False
            )
        return self._local.connection

    def _init_tables(self):
        """Initialize SQLite tables."""
        with self._init_lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    hash TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    model TEXT,
                    dimensions INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_created
                ON embeddings(created_at)
            """)
            conn.commit()

    def _hash_text(self, text: str) -> str:
        """Generate SHA-256 hash for text content."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache (Redis first, then SQLite)."""
        text_hash = self._hash_text(text)

        # Try Redis first (fast)
        if self.redis:
            try:
                cached = self.redis.get_cached_embedding(text_hash)
                if cached is not None:
                    return cached
            except Exception:
                pass  # Redis unavailable, fall through to SQLite

        # Fall back to SQLite
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """SELECT embedding FROM embeddings WHERE hash = ?""",
                (text_hash,)
            )
            row = cursor.fetchone()
            if row:
                embedding = json.loads(row[0])
                # Update access count
                conn.execute(
                    """UPDATE embeddings SET access_count = access_count + 1
                       WHERE hash = ?""",
                    (text_hash,)
                )
                conn.commit()
                # Promote to Redis if available (async-friendly)
                if self.redis:
                    try:
                        self.redis.cache_embedding(text_hash, embedding)
                    except Exception:
                        pass
                return embedding
        except Exception:
            pass

        return None

    def set(
        self,
        text: str,
        embedding: List[float],
        model: Optional[str] = None
    ) -> None:
        """Store embedding in both tiers."""
        text_hash = self._hash_text(text)
        embedding_json = json.dumps(embedding)

        # Store in Redis (hot tier)
        if self.redis:
            try:
                self.redis.cache_embedding(text_hash, embedding)
            except Exception:
                pass

        # Store in SQLite (persistent tier)
        try:
            conn = self._get_connection()
            conn.execute(
                """INSERT OR REPLACE INTO embeddings
                   (hash, embedding, model, dimensions)
                   VALUES (?, ?, ?, ?)""",
                (text_hash, embedding_json, model, len(embedding))
            )
            conn.commit()
        except Exception:
            pass

    def delete(self, text: str) -> bool:
        """Delete embedding from both tiers."""
        text_hash = self._hash_text(text)
        deleted = False

        if self.redis:
            try:
                self.redis.delete_cached_embedding(text_hash)
                deleted = True
            except Exception:
                pass

        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """DELETE FROM embeddings WHERE hash = ?""",
                (text_hash,)
            )
            conn.commit()
            deleted = deleted or cursor.rowcount > 0
        except Exception:
            pass

        return deleted

    def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "sqlite_count": 0,
            "redis_available": False,
        }

        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
            stats["sqlite_count"] = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT SUM(access_count) FROM embeddings"
            )
            stats["total_hits"] = cursor.fetchone()[0] or 0
        except Exception:
            pass

        if self.redis:
            try:
                stats["redis_available"] = self.redis.connected
            except Exception:
                pass

        return stats

    def close(self):
        """Close connections."""
        if hasattr(self._local, 'connection'):
            try:
                self._local.connection.close()
            except Exception:
                pass
