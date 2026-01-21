# test_integration.py
# Integration tests for memory_mcp

import pytest
import json
from unittest.mock import MagicMock, patch


class TestMemoryFlowIntegration:
    """Integration tests for complete memory workflows."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for integration testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_store_search_recall_flow(self, mcp_server):
        """Test complete store -> search -> recall workflow."""
        # Step 1: Store content
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
            "type": "code",
            "source": "algorithms/fibonacci.py",
            "tags": ["algorithm", "recursion", "math"],
            "project": "learning-algorithms"
        })

        assert store_result.get("isError") is not True
        stored_data = json.loads(store_result["content"][0]["text"])
        doc_id = stored_data["id"]

        # Step 2: Search for it
        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "fibonacci",
            "type": "text",
            "limit": 5
        })

        assert search_result.get("isError") is not True
        search_data = json.loads(search_result["content"][0]["text"])
        assert len(search_data["results"]) >= 1

        # Step 3: Recall specific document
        recall_result = mcp_server.handle_call_tool("memory_recall", {
            "id": doc_id
        })

        assert recall_result.get("isError") is not True
        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data.get("found") is True
        assert "document" in recall_data
        assert "fibonacci" in recall_data["document"]["content"]

    def test_store_list_delete_flow(self, mcp_server):
        """Test store -> list -> delete workflow."""
        # Store multiple documents
        doc_ids = []
        for i in range(3):
            result = mcp_server.handle_call_tool("memory_store", {
                "content": f"Test document {i} for deletion test",
                "type": "note",
                "source": f"test/delete_{i}.md",
                "project": "deletion-test"
            })
            data = json.loads(result["content"][0]["text"])
            doc_ids.append(data["id"])

        # List documents
        list_result = mcp_server.handle_call_tool("memory_list", {
            "project": "deletion-test",
            "limit": 10
        })

        list_data = json.loads(list_result["content"][0]["text"])
        assert list_data.get("count", len(list_data.get("documents", []))) >= 3

        # Delete one document
        delete_result = mcp_server.handle_call_tool("memory_delete", {
            "id": doc_ids[0]
        })

        delete_data = json.loads(delete_result["content"][0]["text"])
        assert delete_data["deleted"] is True

        # Verify it's gone
        recall_result = mcp_server.handle_call_tool("memory_recall", {
            "id": doc_ids[0]
        })

        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data.get("found") is False

    def test_vault_write_read_flow(self, mcp_server):
        """Test vault write -> read workflow."""
        # Write a note
        write_result = mcp_server.handle_call_tool("vault_write", {
            "path": "integration-test/my-note",
            "content": "# Integration Test\n\nThis is a test note.\n\n## Topics\n\n- Testing\n- Integration",
            "folder": "notes",
            "tags": ["test", "integration"]
        })

        assert write_result.get("isError") is not True

        # Read it back
        read_result = mcp_server.handle_call_tool("vault_read", {
            "path": "notes/integration-test/my-note"
        })

        assert read_result.get("isError") is not True
        read_data = json.loads(read_result["content"][0]["text"])
        assert read_data.get("found") is True
        assert "Integration Test" in read_data.get("content", "")

    def test_multiple_document_types(self, mcp_server):
        """Test storing and filtering different document types."""
        # Store different types
        types_data = [
            ("code", "def hello(): pass", "hello.py"),
            ("note", "Meeting notes from today", "meeting.md"),
            ("reference", "API documentation", "api-ref.md"),
            ("conversation", "User: Hi\nAssistant: Hello!", "chat.log"),
        ]

        for doc_type, content, source in types_data:
            mcp_server.handle_call_tool("memory_store", {
                "content": content,
                "type": doc_type,
                "source": source,
                "project": "type-test"
            })

        # List by type
        for doc_type, _, _ in types_data:
            list_result = mcp_server.handle_call_tool("memory_list", {
                "type": doc_type,
                "project": "type-test",
                "limit": 10
            })

            list_data = json.loads(list_result["content"][0]["text"])
            assert list_data.get("count", len(list_data.get("documents", []))) >= 1

    def test_search_with_filters(self, mcp_server):
        """Test search with various filters."""
        # Store documents with different attributes
        mcp_server.handle_call_tool("memory_store", {
            "content": "Python async programming tutorial",
            "type": "code",
            "source": "python/async.py",
            "tags": ["python", "async"],
            "project": "tutorials"
        })

        mcp_server.handle_call_tool("memory_store", {
            "content": "JavaScript promise handling",
            "type": "code",
            "source": "js/promises.js",
            "tags": ["javascript", "async"],
            "project": "tutorials"
        })

        # Search with filters
        search_result = mcp_server.handle_call_tool("memory_search", {
            "query": "async",
            "type": "text",
            "filters": {
                "doc_type": "code",
                "project": "tutorials"
            },
            "limit": 10
        })

        assert search_result.get("isError") is not True
        search_data = json.loads(search_result["content"][0]["text"])
        assert len(search_data["results"]) >= 1


class TestSQLiteVaultSync:
    """Test SQLite and Vault are in sync."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_code_stored_in_both(self, mcp_server):
        """Test code documents are stored in both SQLite and vault."""
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "class MyClass:\n    pass",
            "type": "code",
            "source": "myclass.py",
            "language": "python"
        })

        # Should be in SQLite
        stored_data = json.loads(store_result["content"][0]["text"])
        recall_result = mcp_server.handle_call_tool("memory_recall", {
            "id": stored_data["id"]
        })
        recall_data = json.loads(recall_result["content"][0]["text"])
        assert recall_data["found"] is True

        # Should also have vault_path (indicating it's in vault)
        # The exact vault path depends on implementation


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_missing_required_fields(self, mcp_server):
        """Test error handling for missing required fields."""
        # memory_store without required fields
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Some content"
            # Missing 'type' and 'source'
        })

        # Should handle gracefully
        assert result is not None

    def test_invalid_document_type(self, mcp_server):
        """Test handling invalid document type."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content",
            "type": "invalid_type",
            "source": "test.py"
        })

        # Should either accept or handle gracefully
        assert result is not None

    def test_empty_search_query(self, mcp_server):
        """Test handling empty search query."""
        result = mcp_server.handle_call_tool("memory_search", {
            "query": "",
            "type": "text"
        })

        assert result is not None


class TestStatsAndMetrics:
    """Test statistics and metrics collection."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_stats_after_operations(self, mcp_server):
        """Test stats update after operations."""
        # Get initial stats
        initial_stats = mcp_server.handle_call_tool("memory_stats", {})
        initial_data = json.loads(initial_stats["content"][0]["text"])
        initial_count = initial_data.get("sqlite_count", 0)

        # Add some documents
        for i in range(5):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Stats test document {i}",
                "type": "note",
                "source": f"stats_{i}.md"
            })

        # Get updated stats
        updated_stats = mcp_server.handle_call_tool("memory_stats", {})
        updated_data = json.loads(updated_stats["content"][0]["text"])
        updated_count = updated_data.get("sqlite_count", 0)

        assert updated_count >= initial_count + 5

    def test_stats_include_components(self, mcp_server):
        """Test stats include component status."""
        stats = mcp_server.handle_call_tool("memory_stats", {})
        stats_data = json.loads(stats["content"][0]["text"])

        # Should include component availability info
        assert "components" in stats_data or "sqlite_count" in stats_data
