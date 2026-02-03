"""Tests for parallel tier search optimization."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from memory_mcp.tier_manager import TierManager, TierPromotionConfig


class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self, results=None):
        self.results = results or []

    def get_cached_query(self, query: str):
        """Mock cached query retrieval."""
        return self.results


class MockGraphitiManager:
    """Mock Graphiti manager for testing."""

    def __init__(self, results=None):
        self.results = results or []

    async def search_entities(self, query: str, limit: int = 10):
        """Mock entity search."""
        return [
            Mock(
                id=f"entity-{i}",
                name=f"Entity {i}",
                summary=f"Summary for {query}",
                labels=["test"],
            )
            for i in range(min(len(self.results), limit))
        ]


class MockSQLiteIndex:
    """Mock SQLite index for testing."""

    def __init__(self, results=None):
        self.results = results or []

    def search_fulltext(self, query: str, limit: int = 10):
        """Mock fulltext search."""
        return [
            Mock(
                id=f"doc-{i}",
                content=f"Document content for {query}",
                doc_type="note",
                source="test",
            )
            for i in range(min(len(self.results), limit))
        ]


class MockVaultManager:
    """Mock Vault manager for testing."""

    def __init__(self, results=None):
        self.results = results or []

    def search_notes(self, query: str):
        """Mock note search."""
        return [
            Mock(
                id=f"note-{i}",
                content=f"Note content for {query}",
                path=f"notes/note-{i}.md",
                title=f"Note {i}",
                tags=["test"],
            )
            for i in range(len(self.results))
        ]


class TestParallelSearch:
    """Test suite for parallel tier search."""

    def setup_method(self):
        """Setup for each test."""
        self.config = TierPromotionConfig()

    @pytest.mark.asyncio
    async def test_parallel_search_merges_results(self):
        """Test that parallel search returns merged results from all tiers."""
        # Setup mocks with different results
        redis_mock = MockRedisClient([
            {"id": "hot-1", "content": "Hot result", "tier": "hot"}
        ])
        graphiti_mock = MockGraphitiManager([1, 2])  # 2 entities
        sqlite_mock = MockSQLiteIndex([1, 2, 3])  # 3 documents
        vault_mock = MockVaultManager([1])  # 1 note

        manager = TierManager(
            redis=redis_mock,
            graphiti=graphiti_mock,
            sqlite=sqlite_mock,
            vault=vault_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test query", limit=20)

        # Should have results from all tiers
        assert len(results) > 0
        tiers = {r.get('_source_tier') for r in results}
        assert 'hot' in tiers
        assert 'warm' in tiers
        assert 'cold' in tiers
        assert 'archive' in tiers

    @pytest.mark.asyncio
    async def test_parallel_search_deduplicates_by_id(self):
        """Test that duplicate IDs are removed."""
        # Create mock that returns same ID across tiers
        redis_mock = MockRedisClient([
            {"id": "duplicate-1", "content": "Result 1", "score": 0.9}
        ])

        # Mock SQLite to return same ID
        sqlite_mock = Mock()
        sqlite_mock.search_fulltext = Mock(return_value=[
            Mock(
                id="duplicate-1",  # Same ID as Redis
                content="Duplicate content",
                doc_type="note",
                source="test"
            ),
            Mock(
                id="unique-2",
                content="Unique content",
                doc_type="note",
                source="test"
            )
        ])

        manager = TierManager(
            redis=redis_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test", limit=20)

        # Should only have unique IDs
        ids = [r.get('id') for r in results]
        assert len(ids) == len(set(ids)), "Found duplicate IDs"
        assert "duplicate-1" in ids
        assert "unique-2" in ids
        # Should keep only the first occurrence (hot tier)
        duplicate_result = next(r for r in results if r.get('id') == 'duplicate-1')
        assert duplicate_result.get('_source_tier') == 'hot'

    @pytest.mark.asyncio
    async def test_parallel_search_sorts_by_score(self):
        """Test that results are sorted by relevance score."""
        # Create results with different scores
        redis_mock = MockRedisClient([
            {"id": "low", "content": "Low score", "score": 0.3}
        ])

        sqlite_mock = Mock()
        sqlite_mock.search_fulltext = Mock(return_value=[
            Mock(id="high", content="High", doc_type="note", source="test"),
        ])

        manager = TierManager(
            redis=redis_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test", limit=20)

        # Results should be sorted by score (descending)
        scores = [r.get('score', 0) for r in results]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"

    @pytest.mark.asyncio
    async def test_parallel_search_fault_tolerance(self):
        """Test that one tier failing doesn't break others."""
        # Setup mocks where one tier will fail
        redis_mock = MockRedisClient([
            {"id": "good-1", "content": "Good result"}
        ])

        # Graphiti mock that raises exception
        graphiti_mock = Mock()
        graphiti_mock.search_entities = AsyncMock(
            side_effect=Exception("Graphiti connection failed")
        )

        sqlite_mock = MockSQLiteIndex([1, 2])

        manager = TierManager(
            redis=redis_mock,
            graphiti=graphiti_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        # Should not raise exception
        results = await manager.search_all_tiers_parallel("test", limit=20)

        # Should still have results from working tiers
        assert len(results) > 0
        tiers = {r.get('_source_tier') for r in results}
        assert 'hot' in tiers
        assert 'cold' in tiers
        # Warm tier should have failed gracefully
        assert 'warm' not in tiers

    @pytest.mark.asyncio
    async def test_parallel_search_tier_filtering(self):
        """Test that tier filtering works correctly."""
        redis_mock = MockRedisClient([{"id": "hot-1", "content": "Hot"}])
        graphiti_mock = MockGraphitiManager([1])
        sqlite_mock = MockSQLiteIndex([1])
        vault_mock = MockVaultManager([1])

        manager = TierManager(
            redis=redis_mock,
            graphiti=graphiti_mock,
            sqlite=sqlite_mock,
            vault=vault_mock,
            config=self.config
        )

        # Search only hot and cold tiers
        results = await manager.search_all_tiers_parallel(
            "test",
            limit=20,
            tiers=['hot', 'cold']
        )

        tiers = {r.get('_source_tier') for r in results}
        assert 'hot' in tiers
        assert 'cold' in tiers
        assert 'warm' not in tiers
        assert 'archive' not in tiers

    @pytest.mark.asyncio
    async def test_parallel_search_performance(self):
        """Test that parallel search is faster than sequential."""
        import time

        # Create mocks with slight delays
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return [{"id": "result-1", "content": "Result", "score": 0.8}]

        graphiti_mock = Mock()
        graphiti_mock.search_entities = slow_search

        sqlite_mock = Mock()
        sqlite_mock.search_fulltext = lambda *args, **kwargs: (
            [Mock(id="result-2", content="Content", doc_type="note", source="test")]
        )

        manager = TierManager(
            graphiti=graphiti_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        # Measure parallel search time
        start = time.time()
        results = await manager.search_all_tiers_parallel("test", limit=20)
        parallel_time = time.time() - start

        # Parallel search should take roughly the time of the slowest tier (100ms)
        # not the sum of all tiers (200ms+)
        # Allow some overhead but should be significantly faster than sequential
        assert parallel_time < 0.5, f"Parallel search too slow: {parallel_time}s"
        assert len(results) >= 0  # Just ensure it completes

    @pytest.mark.asyncio
    async def test_parallel_search_respects_limit(self):
        """Test that limit parameter is respected."""
        sqlite_mock = MockSQLiteIndex([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        vault_mock = MockVaultManager([1, 2, 3, 4, 5])

        manager = TierManager(
            sqlite=sqlite_mock,
            vault=vault_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test", limit=5)

        # Should not exceed limit
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_parallel_search_empty_results(self):
        """Test behavior with no results from any tier."""
        redis_mock = MockRedisClient([])
        sqlite_mock = MockSQLiteIndex([])

        manager = TierManager(
            redis=redis_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("nonexistent", limit=20)

        assert results == []

    @pytest.mark.asyncio
    async def test_parallel_search_no_tiers_available(self):
        """Test behavior when no tiers are configured."""
        manager = TierManager(config=self.config)

        results = await manager.search_all_tiers_parallel("test", limit=20)

        assert results == []

    @pytest.mark.asyncio
    async def test_parallel_search_preserves_metadata(self):
        """Test that result metadata is preserved."""
        vault_mock = MockVaultManager([1])

        manager = TierManager(
            vault=vault_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test", limit=20)

        if results:
            result = results[0]
            # Check that archive tier metadata is included
            assert 'id' in result
            assert 'content' in result
            assert 'type' in result
            assert 'source' in result
            assert 'score' in result
            assert 'tier' in result
            assert 'match_type' in result
            assert '_source_tier' in result
            assert result['_source_tier'] == 'archive'

    @pytest.mark.asyncio
    async def test_parallel_search_with_vault_notes(self):
        """Test archive tier returns properly formatted vault notes."""
        vault_mock = MockVaultManager([1, 2])

        manager = TierManager(
            vault=vault_mock,
            config=self.config
        )

        results = await manager.search_all_tiers_parallel("test", limit=20)

        # Should have archive results
        archive_results = [r for r in results if r.get('_source_tier') == 'archive']
        assert len(archive_results) > 0

        # Check vault note structure
        for result in archive_results:
            assert 'title' in result
            assert 'tags' in result
            assert isinstance(result['tags'], list)

    @pytest.mark.asyncio
    async def test_parallel_search_concurrent_execution(self):
        """Test that tiers are actually searched concurrently."""
        call_order = []

        async def track_hot(*args, **kwargs):
            call_order.append('hot_start')
            await asyncio.sleep(0.05)
            call_order.append('hot_end')
            return [{"id": "hot-1", "content": "Hot", "score": 0.8}]

        async def track_cold(*args, **kwargs):
            call_order.append('cold_start')
            await asyncio.sleep(0.05)
            call_order.append('cold_end')
            # Return proper dict format, not Mock objects
            return [{"id": "cold-1", "content": "Cold", "doc_type": "note", "source": "test", "score": 0.7}]

        redis_mock = Mock()
        sqlite_mock = Mock()

        manager = TierManager(
            redis=redis_mock,
            sqlite=sqlite_mock,
            config=self.config
        )

        # Patch the helper methods to track execution
        with patch.object(manager, '_search_hot_tier', side_effect=track_hot):
            with patch.object(manager, '_search_cold_tier', side_effect=track_cold):
                await manager.search_all_tiers_parallel("test", limit=20)

        # If concurrent, starts should be before ends
        # (both start before either finishes)
        hot_start_idx = call_order.index('hot_start')
        cold_start_idx = call_order.index('cold_start')
        hot_end_idx = call_order.index('hot_end')

        # Both should start before hot ends (proving concurrency)
        assert hot_start_idx < hot_end_idx
        assert cold_start_idx < hot_end_idx


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
