# test_tier_latency.py
# Benchmark tests validating tier latency SLAs
# Jeremiah Kroesche | Halfservers LLC

import json
import time
import pytest


class TestTierLatency:
    """Benchmark tests validating tier latency SLAs."""

    @pytest.mark.benchmark
    def test_sqlite_search_latency(self, benchmark_server):
        """SQLite FTS search should respond in <100ms."""
        # Setup: Store some documents
        for i in range(10):
            benchmark_server.handle_call_tool("memory_store", {
                "content": f"Benchmark document {i} with searchable content xyz",
                "type": "note",
                "source": f"benchmark_{i}.md"
            })

        # Benchmark search
        start = time.time()
        result = benchmark_server.handle_call_tool("memory_search", {
            "query": "searchable xyz",
            "type": "text",
            "limit": 10
        })
        latency = time.time() - start

        assert result.get("isError") is not True
        assert latency < 0.100, f"SQLite search took {latency*1000:.2f}ms, expected <100ms"

    @pytest.mark.benchmark
    def test_memory_store_latency(self, benchmark_server):
        """Memory store should respond in <50ms."""
        start = time.time()
        result = benchmark_server.handle_call_tool("memory_store", {
            "content": "Quick store test content",
            "type": "note",
            "source": "latency_test.md"
        })
        latency = time.time() - start

        assert result.get("isError") is not True
        assert latency < 0.050, f"Store took {latency*1000:.2f}ms, expected <50ms"

    @pytest.mark.benchmark
    def test_memory_recall_latency(self, benchmark_server):
        """Memory recall should respond in <50ms."""
        # Setup: Store a document
        store_result = benchmark_server.handle_call_tool("memory_store", {
            "content": "Recall test content",
            "type": "note",
            "source": "recall_test.md"
        })
        data = json.loads(store_result["content"][0]["text"])
        doc_id = data["id"]

        # Benchmark recall
        start = time.time()
        result = benchmark_server.handle_call_tool("memory_recall", {
            "id": doc_id
        })
        latency = time.time() - start

        assert result.get("isError") is not True
        assert latency < 0.050, f"Recall took {latency*1000:.2f}ms, expected <50ms"

    @pytest.mark.benchmark
    def test_memory_list_latency(self, benchmark_server):
        """Memory list should respond in <100ms."""
        start = time.time()
        result = benchmark_server.handle_call_tool("memory_list", {
            "limit": 50
        })
        latency = time.time() - start

        assert result.get("isError") is not True
        assert latency < 0.100, f"List took {latency*1000:.2f}ms, expected <100ms"

    @pytest.mark.benchmark
    def test_memory_stats_latency(self, benchmark_server):
        """Memory stats should respond in <100ms."""
        start = time.time()
        result = benchmark_server.handle_call_tool("memory_stats", {})
        latency = time.time() - start

        assert result.get("isError") is not True
        assert latency < 0.100, f"Stats took {latency*1000:.2f}ms, expected <100ms"


class TestThroughput:
    """Benchmark tests for throughput under load."""

    @pytest.mark.benchmark
    def test_batch_store_throughput(self, benchmark_server):
        """Test storing many documents in sequence."""
        count = 100
        start = time.time()

        for i in range(count):
            result = benchmark_server.handle_call_tool("memory_store", {
                "content": f"Throughput test document {i}",
                "type": "note",
                "source": f"throughput_{i}.md"
            })
            assert result.get("isError") is not True

        total_time = time.time() - start
        ops_per_second = count / total_time

        # Should handle at least 50 stores per second
        assert ops_per_second >= 50, (
            f"Only {ops_per_second:.1f} ops/sec, expected >=50"
        )

    @pytest.mark.benchmark
    def test_batch_search_throughput(self, benchmark_server):
        """Test searching many times in sequence."""
        # Setup: Store some documents
        for i in range(20):
            benchmark_server.handle_call_tool("memory_store", {
                "content": f"Search throughput content {i} with keyword alpha",
                "type": "note",
                "source": f"search_throughput_{i}.md"
            })

        count = 50
        start = time.time()

        for i in range(count):
            result = benchmark_server.handle_call_tool("memory_search", {
                "query": "alpha",
                "type": "text",
                "limit": 10
            })
            assert result.get("isError") is not True

        total_time = time.time() - start
        ops_per_second = count / total_time

        # Should handle at least 20 searches per second
        assert ops_per_second >= 20, (
            f"Only {ops_per_second:.1f} ops/sec, expected >=20"
        )


class TestMemoryUsage:
    """Benchmark tests for memory efficiency."""

    @pytest.mark.benchmark
    def test_large_document_storage(self, benchmark_server):
        """Test storing large documents doesn't cause issues."""
        # Store 10 documents of 10KB each
        large_content = "x" * 10240  # 10KB

        for i in range(10):
            result = benchmark_server.handle_call_tool("memory_store", {
                "content": f"Header {i}\n{large_content}",
                "type": "note",
                "source": f"large_{i}.md"
            })
            assert result.get("isError") is not True

        # Verify they're searchable
        search_result = benchmark_server.handle_call_tool("memory_search", {
            "query": "Header",
            "type": "text",
            "limit": 20
        })
        assert search_result.get("isError") is not True
        data = json.loads(search_result["content"][0]["text"])
        assert len(data["results"]) >= 1

    @pytest.mark.benchmark
    def test_many_small_documents(self, benchmark_server):
        """Test storing many small documents."""
        # Store 500 small documents
        for i in range(500):
            result = benchmark_server.handle_call_tool("memory_store", {
                "content": f"Small doc {i}",
                "type": "note",
                "source": f"small_{i}.md"
            })
            assert result.get("isError") is not True

        # Verify stats work with many docs
        stats_result = benchmark_server.handle_call_tool("memory_stats", {})
        assert stats_result.get("isError") is not True
        stats_data = json.loads(stats_result["content"][0]["text"])
        assert stats_data.get("sqlite_count", 0) >= 500


class TestStatsCollector:
    """Tests for the stats collector."""

    def test_stats_collector_record(self):
        """Test recording operations to stats collector."""
        from memory_mcp.stats_collector import StatsCollector
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            collector = StatsCollector(stats_path=Path(tmp) / "test_stats.json")

            # Record some operations
            collector.record_operation("sqlite", 5.5, success=True)
            collector.record_operation("sqlite", 3.2, success=True)
            collector.record_operation("sqlite", 10.0, success=False)

            stats = collector.get_stats()
            sqlite_stats = stats.get("sqlite", {})

            assert sqlite_stats.get("operation_count") == 3
            assert sqlite_stats.get("error_count") == 1
            assert sqlite_stats.get("avg_latency_ms") == pytest.approx(6.23, rel=0.1)

    def test_stats_collector_summary(self):
        """Test generating human-readable summary."""
        from memory_mcp.stats_collector import StatsCollector
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            collector = StatsCollector(stats_path=Path(tmp) / "test_stats.json")

            collector.record_operation("redis", 0.5, success=True)
            collector.record_operation("sqlite", 5.0, success=True)

            summary = collector.get_summary()

            assert "redis" in summary
            assert "sqlite" in summary
            assert "Memory Tier Statistics" in summary


class TestAccessTracker:
    """Tests for the access tracker."""

    def test_access_tracker_record(self):
        """Test recording document access."""
        from memory_mcp.access_tracker import AccessTracker

        tracker = AccessTracker()

        # Record accesses
        tracker.record_access("doc-1", size=100)
        tracker.record_access("doc-1", size=100)
        tracker.record_access("doc-1", size=100)

        stats = tracker.get_stats("doc-1")

        assert stats.access_count == 3
        assert stats.content_size == 100
        assert stats.last_access is not None

    def test_access_tracker_hot_documents(self):
        """Test getting hot documents."""
        from memory_mcp.access_tracker import AccessTracker

        tracker = AccessTracker()

        # Create hot and cold documents
        for _ in range(10):
            tracker.record_access("hot-doc", size=100)

        for _ in range(2):
            tracker.record_access("cold-doc", size=100)

        hot_docs = tracker.get_hot_documents(threshold=5)

        assert len(hot_docs) == 1
        assert hot_docs[0][0] == "hot-doc"
        assert hot_docs[0][1] == 10


class TestTierManager:
    """Tests for the tier manager."""

    def test_tier_manager_should_promote(self, benchmark_config):
        """Test promotion threshold checking."""
        from memory_mcp.tier_manager import TierManager, TierPromotionConfig
        from memory_mcp.sqlite_index import SQLiteIndex

        sqlite = SQLiteIndex(config=benchmark_config.sqlite)
        config = TierPromotionConfig(promotion_threshold=3, min_size_for_extraction=50)
        manager = TierManager(sqlite=sqlite, config=config)

        # Record accesses below threshold
        manager.record_access("doc-1", content_size=100)
        manager.record_access("doc-1", content_size=100)
        assert not manager.should_promote_to_warm("doc-1")

        # Record to meet threshold
        manager.record_access("doc-1", content_size=100)
        # Without graphiti, shouldn't promote
        assert not manager.should_promote_to_warm("doc-1")

    def test_tier_manager_stats(self, benchmark_config):
        """Test getting tier statistics."""
        from memory_mcp.tier_manager import TierManager
        from memory_mcp.sqlite_index import SQLiteIndex

        sqlite = SQLiteIndex(config=benchmark_config.sqlite)
        manager = TierManager(sqlite=sqlite)

        stats = manager.get_tier_stats()

        assert "tiers" in stats
        assert "cold" in stats["tiers"]
        assert stats["tiers"]["cold"]["available"] is True
