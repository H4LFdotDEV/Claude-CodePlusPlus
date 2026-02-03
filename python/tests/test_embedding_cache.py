"""Tests for UnifiedEmbeddingCache with Redis + SQLite fallback."""

import os
import tempfile
import threading
import time
from typing import List
from unittest.mock import Mock, patch

import pytest

from shared.embedding_cache import UnifiedEmbeddingCache


@pytest.fixture
def temp_sqlite_path():
    """Create temporary SQLite database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "embeddings.db")


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = Mock()
    redis.connected = True
    redis.get_cached_embedding = Mock(return_value=None)
    redis.cache_embedding = Mock()
    redis.delete_cached_embedding = Mock()
    return redis


@pytest.fixture
def cache_with_redis(mock_redis, temp_sqlite_path):
    """Create cache with mock Redis."""
    cache = UnifiedEmbeddingCache(redis=mock_redis, sqlite_path=temp_sqlite_path)
    yield cache
    cache.close()


@pytest.fixture
def cache_without_redis(temp_sqlite_path):
    """Create cache without Redis (SQLite-only)."""
    cache = UnifiedEmbeddingCache(redis=None, sqlite_path=temp_sqlite_path)
    yield cache
    cache.close()


class TestBasicOperations:
    """Test basic get/set/delete operations."""

    def test_set_and_get_with_redis(self, cache_with_redis, mock_redis):
        """Test storing and retrieving embeddings with Redis."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3, 0.4]

        # Set embedding
        cache_with_redis.set(text, embedding, model="text-embedding-3-small")

        # Verify both tiers were called
        assert mock_redis.cache_embedding.called

        # Mock Redis returning the embedding
        mock_redis.get_cached_embedding.return_value = embedding

        # Get embedding (should hit Redis)
        result = cache_with_redis.get(text)
        assert result == embedding
        assert mock_redis.get_cached_embedding.called

    def test_set_and_get_without_redis(self, cache_without_redis):
        """Test SQLite-only operations."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3, 0.4]

        # Set embedding
        cache_without_redis.set(text, embedding, model="text-embedding-3-small")

        # Get embedding (should hit SQLite)
        result = cache_without_redis.get(text)
        assert result == embedding

    def test_get_nonexistent(self, cache_with_redis):
        """Test getting non-existent embedding returns None."""
        result = cache_with_redis.get("nonexistent")
        assert result is None

    def test_delete_embedding(self, cache_with_redis, mock_redis):
        """Test deleting embedding from both tiers."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        # Set and delete
        cache_with_redis.set(text, embedding)
        deleted = cache_with_redis.delete(text)

        assert deleted
        assert mock_redis.delete_cached_embedding.called

        # Verify it's gone
        result = cache_with_redis.get(text)
        assert result is None


class TestRedisFailover:
    """Test SQLite fallback when Redis is unavailable."""

    def test_redis_get_failure_falls_back_to_sqlite(self, cache_with_redis, mock_redis):
        """Test fallback to SQLite when Redis get fails."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        # Store in SQLite only (simulate Redis failure during set)
        mock_redis.cache_embedding.side_effect = Exception("Redis unavailable")
        cache_with_redis.set(text, embedding)

        # Redis get fails
        mock_redis.get_cached_embedding.side_effect = Exception("Redis unavailable")

        # Should fall back to SQLite
        result = cache_with_redis.get(text)
        assert result == embedding

    def test_redis_unavailable_during_set(self, cache_with_redis, mock_redis):
        """Test that set succeeds even if Redis fails."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        mock_redis.cache_embedding.side_effect = Exception("Redis unavailable")
        mock_redis.get_cached_embedding.return_value = None

        # Should not raise exception
        cache_with_redis.set(text, embedding)

        # Should still be in SQLite
        result = cache_with_redis.get(text)
        assert result == embedding


class TestPromotion:
    """Test automatic promotion from SQLite to Redis."""

    def test_sqlite_hit_promotes_to_redis(self, cache_with_redis, mock_redis):
        """Test that SQLite hits promote to Redis."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        # Store only in SQLite (simulate Redis failure)
        mock_redis.cache_embedding.side_effect = [Exception("Fail"), None]
        cache_with_redis.set(text, embedding)

        # Redis miss, SQLite hit
        mock_redis.get_cached_embedding.return_value = None
        result = cache_with_redis.get(text)

        assert result == embedding
        # Should attempt to promote to Redis
        assert mock_redis.cache_embedding.call_count >= 2

    def test_access_count_increments(self, cache_without_redis):
        """Test that access count increments on SQLite hits."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        cache_without_redis.set(text, embedding)

        # Access multiple times
        for _ in range(5):
            cache_without_redis.get(text)

        # Check stats
        stats = cache_without_redis.get_stats()
        assert stats["total_hits"] >= 5


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_writes(self, cache_without_redis):
        """Test concurrent writes from multiple threads."""
        num_threads = 10
        embeddings_per_thread = 10
        results = []

        def write_embeddings(thread_id: int):
            for i in range(embeddings_per_thread):
                text = f"thread_{thread_id}_doc_{i}"
                embedding = [float(thread_id), float(i)]
                cache_without_redis.set(text, embedding)

        threads = []
        for tid in range(num_threads):
            thread = threading.Thread(target=write_embeddings, args=(tid,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all embeddings were stored
        stats = cache_without_redis.get_stats()
        assert stats["sqlite_count"] == num_threads * embeddings_per_thread

    def test_concurrent_reads(self, cache_without_redis):
        """Test concurrent reads from multiple threads."""
        text = "shared_document"
        embedding = [0.1, 0.2, 0.3]
        cache_without_redis.set(text, embedding)

        results = []

        def read_embedding():
            result = cache_without_redis.get(text)
            results.append(result)

        threads = []
        for _ in range(20):
            thread = threading.Thread(target=read_embedding)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same embedding
        assert len(results) == 20
        assert all(r == embedding for r in results)

    def test_thread_local_connections(self, cache_without_redis):
        """Test that each thread gets its own SQLite connection."""
        connection_ids = []

        def get_connection_id():
            conn = cache_without_redis._get_connection()
            connection_ids.append(id(conn))

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=get_connection_id)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Each thread should have a unique connection
        assert len(set(connection_ids)) == 5


class TestStats:
    """Test statistics reporting."""

    def test_stats_with_redis(self, cache_with_redis, mock_redis):
        """Test stats when Redis is available."""
        text1 = "doc1"
        text2 = "doc2"
        embedding1 = [0.1, 0.2]
        embedding2 = [0.3, 0.4]

        cache_with_redis.set(text1, embedding1)
        cache_with_redis.set(text2, embedding2)

        stats = cache_with_redis.get_stats()
        assert stats["sqlite_count"] == 2
        assert stats["redis_available"] is True

    def test_stats_without_redis(self, cache_without_redis):
        """Test stats when Redis is not available."""
        text = "doc"
        embedding = [0.1, 0.2]

        cache_without_redis.set(text, embedding)
        cache_without_redis.get(text)

        stats = cache_without_redis.get_stats()
        assert stats["sqlite_count"] == 1
        assert stats["redis_available"] is False
        assert stats["total_hits"] >= 1

    def test_stats_after_deletes(self, cache_without_redis):
        """Test stats reflect deletions."""
        embeddings = {
            f"doc{i}": [float(i), float(i + 1)]
            for i in range(5)
        }

        for text, emb in embeddings.items():
            cache_without_redis.set(text, emb)

        # Delete some
        cache_without_redis.delete("doc0")
        cache_without_redis.delete("doc1")

        stats = cache_without_redis.get_stats()
        assert stats["sqlite_count"] == 3


class TestHashConsistency:
    """Test hash generation consistency."""

    def test_same_text_same_hash(self, cache_without_redis):
        """Test same text produces same hash."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]

        cache_without_redis.set(text, embedding)
        result1 = cache_without_redis.get(text)
        result2 = cache_without_redis.get(text)

        assert result1 == result2 == embedding

    def test_different_text_different_hash(self, cache_without_redis):
        """Test different texts produce different hashes."""
        text1 = "document one"
        text2 = "document two"
        embedding1 = [0.1, 0.2]
        embedding2 = [0.3, 0.4]

        cache_without_redis.set(text1, embedding1)
        cache_without_redis.set(text2, embedding2)

        result1 = cache_without_redis.get(text1)
        result2 = cache_without_redis.get(text2)

        assert result1 == embedding1
        assert result2 == embedding2
        assert result1 != result2

    def test_unicode_handling(self, cache_without_redis):
        """Test unicode text is handled correctly."""
        text = "测试文档 🚀"
        embedding = [0.1, 0.2, 0.3]

        cache_without_redis.set(text, embedding)
        result = cache_without_redis.get(text)

        assert result == embedding


class TestModelMetadata:
    """Test model metadata storage."""

    def test_store_model_info(self, cache_without_redis):
        """Test storing model information with embeddings."""
        text = "test document"
        embedding = [0.1, 0.2, 0.3]
        model = "text-embedding-3-small"

        cache_without_redis.set(text, embedding, model=model)

        # Verify stored in database
        conn = cache_without_redis._get_connection()
        cursor = conn.execute(
            "SELECT model, dimensions FROM embeddings WHERE hash = ?",
            (cache_without_redis._hash_text(text),)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == model
        assert row[1] == len(embedding)

    def test_update_replaces_model_info(self, cache_without_redis):
        """Test updating embedding replaces model info."""
        text = "test document"
        embedding1 = [0.1, 0.2]
        embedding2 = [0.1, 0.2, 0.3, 0.4]

        cache_without_redis.set(text, embedding1, model="old-model")
        cache_without_redis.set(text, embedding2, model="new-model")

        conn = cache_without_redis._get_connection()
        cursor = conn.execute(
            "SELECT model, dimensions FROM embeddings WHERE hash = ?",
            (cache_without_redis._hash_text(text),)
        )
        row = cursor.fetchone()

        assert row[0] == "new-model"
        assert row[1] == 4


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_embedding(self, cache_without_redis):
        """Test storing empty embedding."""
        text = "empty"
        embedding: List[float] = []

        cache_without_redis.set(text, embedding)
        result = cache_without_redis.get(text)

        assert result == []

    def test_large_embedding(self, cache_without_redis):
        """Test storing large embedding (e.g., 1536 dimensions)."""
        text = "large document"
        embedding = [float(i) for i in range(1536)]

        cache_without_redis.set(text, embedding)
        result = cache_without_redis.get(text)

        assert result == embedding
        assert len(result) == 1536

    def test_very_long_text(self, cache_without_redis):
        """Test hashing very long text."""
        text = "a" * 100000  # 100KB of text
        embedding = [0.1, 0.2, 0.3]

        cache_without_redis.set(text, embedding)
        result = cache_without_redis.get(text)

        assert result == embedding

    def test_delete_nonexistent(self, cache_without_redis):
        """Test deleting non-existent embedding."""
        deleted = cache_without_redis.delete("nonexistent")
        # Should return False or not crash
        assert deleted is False

    def test_close_cleanup(self, temp_sqlite_path):
        """Test proper cleanup on close."""
        cache = UnifiedEmbeddingCache(redis=None, sqlite_path=temp_sqlite_path)
        cache.set("test", [0.1, 0.2])

        cache.close()

        # Connection should be closed
        # New cache should still be able to read the data
        cache2 = UnifiedEmbeddingCache(redis=None, sqlite_path=temp_sqlite_path)
        result = cache2.get("test")
        assert result == [0.1, 0.2]
        cache2.close()


class TestPerformance:
    """Test performance characteristics."""

    def test_batch_write_performance(self, cache_without_redis):
        """Test writing many embeddings."""
        start = time.time()

        for i in range(100):
            text = f"document_{i}"
            embedding = [float(i), float(i + 1)]
            cache_without_redis.set(text, embedding)

        duration = time.time() - start

        # Should complete in reasonable time (< 1 second for 100 writes)
        assert duration < 1.0

        stats = cache_without_redis.get_stats()
        assert stats["sqlite_count"] == 100

    def test_batch_read_performance(self, cache_without_redis):
        """Test reading many embeddings."""
        # Pre-populate
        for i in range(100):
            cache_without_redis.set(f"doc_{i}", [float(i)])

        start = time.time()

        for i in range(100):
            cache_without_redis.get(f"doc_{i}")

        duration = time.time() - start

        # Should complete in reasonable time (< 0.5 seconds for 100 reads)
        assert duration < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
