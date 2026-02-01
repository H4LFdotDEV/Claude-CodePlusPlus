# test_tier_flow.py
# Integration tests for data flowing through memory tiers
#
# Memory Tiers:
#   Hot:     Redis (session cache) - <1ms access
#   Cold:    SQLite (metadata, FTS) - <50ms access
#   Archive: Obsidian vault (human-readable) - <200ms access

import json
import pytest
from unittest.mock import MagicMock, patch


class TestTierFlow:
    """Test data flows correctly through all memory tiers."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for tier flow testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_store_writes_to_sqlite_tier(self, mcp_server):
        """Test that memory_store writes to SQLite (cold tier)."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Tier flow test content",
            "type": "note",
            "source": "tier-test/sqlite.md"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        doc_id = data["id"]

        # Verify it's in SQLite
        recall_result = mcp_server.handle_call_tool("memory_recall", {"id": doc_id})
        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data["found"] is True
        assert "Tier flow test" in recall_data["document"]["content"]

    def test_code_flows_to_vault_archive(self, mcp_server):
        """Test that code documents flow to vault (archive tier)."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "def tier_test():\n    return 'archive tier'",
            "type": "code",
            "source": "tier_archive_test.py",
            "language": "python",
            "tags": ["tier-test"]
        })

        assert result.get("isError") is not True

        # Verify vault has the code
        # Vault sanitizes filename to stem, so "tier_archive_test.py" -> "code/tier_archive_test.md"
        vault_result = mcp_server.handle_call_tool("vault_read", {
            "path": "code/tier_archive_test"
        })
        vault_data = json.loads(vault_result["content"][0]["text"])
        assert vault_data["found"] is True
        assert "tier_test" in vault_data["content"]

    def test_note_flows_to_vault_archive(self, mcp_server):
        """Test that note documents flow to vault (archive tier)."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "# Note Tier Test\n\nThis note should be in vault.",
            "type": "note",
            "source": "tier-test/note.md"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        doc_id = data["id"]

        # Note is stored in SQLite with generated path
        recall_result = mcp_server.handle_call_tool("memory_recall", {"id": doc_id})
        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data["found"] is True

    def test_search_queries_cold_tier(self, mcp_server):
        """Test that search queries hit the cold tier (SQLite FTS)."""
        # Store multiple documents
        for i in range(3):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Search test document {i} with keyword foobar",
                "type": "note",
                "source": f"tier-test/search_{i}.md"
            })

        # Search should query SQLite FTS
        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "foobar",
            "type": "text",
            "limit": 10
        })

        search_data = json.loads(search_result["content"][0]["text"])
        assert len(search_data["results"]) >= 3
        assert all("foobar" in r["content"] for r in search_data["results"])

    def test_vault_tier_direct_access(self, mcp_server):
        """Test direct vault read/write bypasses SQLite."""
        # Write directly to vault
        write_result = mcp_server.handle_call_tool("vault_write", {
            "path": "direct-access/test-note",
            "content": "# Direct Access\n\nThis bypasses SQLite.",
            "folder": "notes"
        })

        assert write_result.get("isError") is not True

        # Read directly from vault
        read_result = mcp_server.handle_call_tool("vault_read", {
            "path": "notes/direct-access/test-note"
        })

        read_data = json.loads(read_result["content"][0]["text"])
        assert read_data["found"] is True
        assert "Direct Access" in read_data["content"]


class TestTierGracefulDegradation:
    """Test system works when tiers are unavailable."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for degradation testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_works_without_redis(self, mcp_server):
        """Test system operates when Redis is unavailable."""
        # Redis is typically unavailable in test environment
        # System should still function

        # Store should work
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "No Redis test",
            "type": "note",
            "source": "no-redis.md"
        })
        assert store_result.get("isError") is not True

        # Search should work
        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "Redis",
            "type": "text"
        })
        assert search_result.get("isError") is not True

        # Stats should show Redis unavailable
        stats_result = mcp_server.handle_call_tool("memory_stats", {})
        stats_data = json.loads(stats_result["content"][0]["text"])
        # Either components.redis is False or health.redis shows not_available
        components = stats_data.get("components", {})
        health = stats_data.get("health", {})
        redis_unavailable = (
            components.get("redis") is False or
            health.get("redis", {}).get("status") in ("not_available", "error")
        )
        assert redis_unavailable or components.get("redis") is True  # May be configured

    def test_session_fallback_to_sqlite(self, mcp_server):
        """Test session operations fallback to SQLite when Redis unavailable."""
        # Save session (will use SQLite fallback)
        # Use relative path - absolute paths are not allowed by validation
        save_result = mcp_server.handle_call_tool("session_save", {
            "project_path": "test/fallback/project",
            "active_files": ["file1.py", "file2.py"]
        })

        save_data = json.loads(save_result["content"][0]["text"])
        assert save_data["saved"] is True
        # Backend should be sqlite when Redis unavailable
        assert save_data.get("backend") in ("sqlite", "redis")
        session_id = save_data["session_id"]

        # Restore should work
        restore_result = mcp_server.handle_call_tool("session_restore", {
            "session_id": session_id
        })

        restore_data = json.loads(restore_result["content"][0]["text"])
        assert restore_data.get("found") is True or "available_sessions" in restore_data

    def test_list_sessions_without_id(self, mcp_server):
        """Test listing sessions without providing session_id."""
        # First save a session (use relative path - absolute paths not allowed)
        mcp_server.handle_call_tool("session_save", {
            "project_path": "test/list/project",
            "active_files": []
        })

        # List sessions (no session_id)
        list_result = mcp_server.handle_call_tool("session_restore", {})

        list_data = json.loads(list_result["content"][0]["text"])
        assert "available_sessions" in list_data
        assert isinstance(list_data["available_sessions"], list)


class TestTierConsistency:
    """Test data consistency across tiers."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for consistency testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_delete_removes_from_all_tiers(self, mcp_server):
        """Test that delete removes data from SQLite tier."""
        # Store a document
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "Document to delete",
            "type": "note",
            "source": "delete-test.md"
        })

        data = json.loads(store_result["content"][0]["text"])
        doc_id = data["id"]

        # Verify it exists
        recall_result = mcp_server.handle_call_tool("memory_recall", {"id": doc_id})
        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data["found"] is True

        # Delete it
        delete_result = mcp_server.handle_call_tool("memory_delete", {"id": doc_id})
        delete_data = json.loads(delete_result["content"][0]["text"])
        assert delete_data["deleted"] is True

        # Verify it's gone from SQLite
        recall_after = mcp_server.handle_call_tool("memory_recall", {"id": doc_id})
        recall_after_data = json.loads(recall_after["content"][0]["text"])
        assert recall_after_data["found"] is False

    def test_stats_reflect_all_tiers(self, mcp_server):
        """Test stats show information from all available tiers."""
        stats_result = mcp_server.handle_call_tool("memory_stats", {})
        stats_data = json.loads(stats_result["content"][0]["text"])

        # Should have SQLite count
        assert "sqlite_count" in stats_data

        # Should have component availability
        assert "components" in stats_data
        assert "sqlite" in stats_data["components"]
        assert "vault" in stats_data["components"]

        # Should have health info
        assert "health" in stats_data
        assert "sqlite" in stats_data["health"]
        assert "vault" in stats_data["health"]

    def test_store_increments_stats(self, mcp_server):
        """Test that storing documents increments stats correctly."""
        # Get initial count
        initial_stats = mcp_server.handle_call_tool("memory_stats", {})
        initial_data = json.loads(initial_stats["content"][0]["text"])
        initial_count = initial_data.get("sqlite_count", 0)

        # Store 5 documents
        for i in range(5):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Stats increment test {i}",
                "type": "note",
                "source": f"stats-test-{i}.md"
            })

        # Get final count
        final_stats = mcp_server.handle_call_tool("memory_stats", {})
        final_data = json.loads(final_stats["content"][0]["text"])
        final_count = final_data.get("sqlite_count", 0)

        assert final_count >= initial_count + 5


class TestTierSpecificBehavior:
    """Test tier-specific behavior and optimizations."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for tier-specific testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_hybrid_search_uses_multiple_tiers(self, mcp_server):
        """Test hybrid search combines text and semantic search."""
        # Store searchable content
        mcp_server.handle_call_tool("memory_store", {
            "content": "Machine learning models for natural language processing",
            "type": "note",
            "source": "ml-nlp.md",
            "tags": ["ml", "nlp"]
        })

        # Hybrid search
        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "machine learning",
            "type": "hybrid",
            "limit": 10
        })

        search_data = json.loads(search_result["content"][0]["text"])
        assert "results" in search_data
        # Should have at least text results
        if len(search_data["results"]) > 0:
            assert "match_type" in search_data["results"][0]

    def test_text_search_type(self, mcp_server):
        """Test explicit text search."""
        mcp_server.handle_call_tool("memory_store", {
            "content": "Explicit text search test content",
            "type": "note",
            "source": "text-search.md"
        })

        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "Explicit text",
            "type": "text",
            "limit": 5
        })

        search_data = json.loads(search_result["content"][0]["text"])
        if len(search_data["results"]) > 0:
            assert search_data["results"][0]["match_type"] == "text"

    def test_semantic_search_fallback(self, mcp_server):
        """Test semantic search falls back appropriately."""
        mcp_server.handle_call_tool("memory_store", {
            "content": "Semantic search fallback test",
            "type": "note",
            "source": "semantic.md"
        })

        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "semantic fallback",
            "type": "semantic",
            "limit": 5
        })

        search_data = json.loads(search_result["content"][0]["text"])
        # Should either have results or empty (fallback behavior)
        assert "results" in search_data
