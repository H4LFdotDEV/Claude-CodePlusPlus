# test_api_health.py
# Comprehensive API Health Verification Tests for Memory MCP Server
# Tests all 10 endpoints, component health, graceful degradation, and performance

import pytest
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch


class TestEndpointAvailability:
    """Verify all 10 MCP endpoints are operational and return valid responses."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_memory_store_endpoint_available(self, mcp_server):
        """Test memory_store endpoint responds with valid structure."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Health check test content",
            "type": "note",
            "source": "health_check/store.py",
        })

        assert result.get("isError") is not True
        assert "content" in result
        assert len(result["content"]) > 0
        data = json.loads(result["content"][0]["text"])
        assert "id" in data
        assert isinstance(data["id"], str)
        assert len(data["id"]) > 0

    def test_memory_search_endpoint_available(self, mcp_server):
        """Test memory_search endpoint responds with valid structure."""
        # Store something first
        mcp_server.handle_call_tool("memory_store", {
            "content": "Searchable health check content",
            "type": "note",
            "source": "health_check/search.py",
        })

        result = mcp_server.handle_call_tool("memory_search", {
            "query": "health check",
            "type": "text",
            "limit": 10
        })

        assert result.get("isError") is not True
        assert "content" in result
        data = json.loads(result["content"][0]["text"])
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)

    def test_memory_recall_endpoint_available(self, mcp_server):
        """Test memory_recall endpoint responds with valid structure."""
        # Store first
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content to recall",
            "type": "note",
            "source": "health_check/recall.py",
        })
        doc_id = json.loads(store_result["content"][0]["text"])["id"]

        result = mcp_server.handle_call_tool("memory_recall", {
            "id": doc_id
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "found" in data
        assert data["found"] is True
        assert "document" in data

    def test_memory_delete_endpoint_available(self, mcp_server):
        """Test memory_delete endpoint responds with valid structure."""
        # Store first
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content to delete",
            "type": "note",
            "source": "health_check/delete.py",
        })
        doc_id = json.loads(store_result["content"][0]["text"])["id"]

        result = mcp_server.handle_call_tool("memory_delete", {
            "id": doc_id
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "deleted" in data
        assert data["deleted"] is True

    def test_memory_list_endpoint_available(self, mcp_server):
        """Test memory_list endpoint responds with valid structure."""
        # Store some documents first
        for i in range(3):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"List test document {i}",
                "type": "note",
                "source": f"health_check/list_{i}.py",
            })

        result = mcp_server.handle_call_tool("memory_list", {
            "limit": 20
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "documents" in data or "count" in data

    def test_session_save_endpoint_available(self, mcp_server):
        """Test session_save endpoint responds with valid structure."""
        result = mcp_server.handle_call_tool("session_save", {
            "project_path": "health_check/project",
            "active_files": ["file1.py", "file2.py"],
            "context": {"test": "health_check"}
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "session_id" in data or "saved" in data

    def test_session_restore_endpoint_available(self, mcp_server):
        """Test session_restore endpoint responds with valid structure."""
        # Save first
        save_result = mcp_server.handle_call_tool("session_save", {
            "project_path": "health_check/restore_project",
        })

        result = mcp_server.handle_call_tool("session_restore", {})

        assert result.get("isError") is not True
        # Should return either session data or indicate no session found

    def test_vault_write_endpoint_available(self, mcp_server):
        """Test vault_write endpoint responds with valid structure."""
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "health-check-note",
            "content": "# Health Check\n\nTest content for vault write.",
            "folder": "notes",
            "tags": ["health", "check"]
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "written" in data or "path" in data

    def test_vault_read_endpoint_available(self, mcp_server):
        """Test vault_read endpoint responds with valid structure."""
        # Write first
        mcp_server.handle_call_tool("vault_write", {
            "path": "health-check-read-test",
            "content": "Content for reading",
        })

        result = mcp_server.handle_call_tool("vault_read", {
            "path": "health-check-read-test"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "found" in data

    def test_memory_stats_endpoint_available(self, mcp_server):
        """Test memory_stats endpoint responds with valid structure."""
        result = mcp_server.handle_call_tool("memory_stats", {})

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "sqlite_count" in data or "components" in data


class TestComponentHealthChecks:
    """Test component availability detection and health checking."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_sqlite_health_available(self, mcp_server):
        """Test SQLite component is available and healthy."""
        assert mcp_server.sqlite is not None

        # SQLite should be operational
        stats = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(stats["content"][0]["text"])

        # Should have sqlite_count indicating SQLite is working
        assert "sqlite_count" in data
        assert isinstance(data["sqlite_count"], int)
        assert data["sqlite_count"] >= 0

    def test_vault_health_available(self, mcp_server):
        """Test Vault component is available and healthy."""
        assert mcp_server.vault is not None

        # Write and read should work
        write_result = mcp_server.handle_call_tool("vault_write", {
            "path": "vault-health-test",
            "content": "Health check",
        })
        assert write_result.get("isError") is not True

    def test_redis_health_when_available(self, test_config, mock_redis):
        """Test Redis health check when Redis is available."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", True):
            with patch("memory_mcp.server.RedisClient") as MockRedis:
                mock_client = MagicMock()
                mock_client.connect.return_value = True
                mock_client.health_check.return_value = True
                # Provide actual JSON-serializable stats
                mock_client.get_stats.return_value = {
                    "connected": True,
                    "cache_hits": 100,
                    "cache_misses": 10
                }
                MockRedis.return_value = mock_client

                from memory_mcp.server import MemoryMCPServer
                server = MemoryMCPServer(config=test_config)

                stats = server.handle_call_tool("memory_stats", {})
                data = json.loads(stats["content"][0]["text"])

                # Should indicate Redis availability in components
                assert "components" in data
                assert data["components"]["redis"] is True

    def test_components_section_in_stats(self, test_config):
        """Test stats includes components section."""
        from memory_mcp.server import MemoryMCPServer
        server = MemoryMCPServer(config=test_config)

        stats = server.handle_call_tool("memory_stats", {})
        data = json.loads(stats["content"][0]["text"])

        # Should include components section
        assert "components" in data
        assert "sqlite" in data["components"]
        assert "vault" in data["components"]

    def test_embedder_health_check(self, test_config, mock_embedding_provider):
        """Test embedding provider health when available."""
        with patch("memory_mcp.server.get_embedding_provider") as mock_get_provider:
            mock_get_provider.return_value = mock_embedding_provider

            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            # Embedder should be initialized - verify no crash during init
            assert server is not None


class TestGracefulDegradation:
    """Verify system works correctly when optional components are unavailable."""

    def test_search_without_redis(self, test_config):
        """Test memory operations work when Redis is unavailable."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", False):
            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            # Store should work without Redis
            store_result = server.handle_call_tool("memory_store", {
                "content": "Content without Redis",
                "type": "note",
                "source": "no_redis.py",
            })
            assert store_result.get("isError") is not True

            # Search should work (text search at minimum)
            search_result = server.handle_call_tool("memory_search", {
                "query": "Redis",
                "type": "text",
                "limit": 10
            })
            assert search_result.get("isError") is not True

    def test_text_search_always_available(self, test_config):
        """Test text search works independently of optional components."""
        from memory_mcp.server import MemoryMCPServer
        server = MemoryMCPServer(config=test_config)

        # Store content
        server.handle_call_tool("memory_store", {
            "content": "Content for text search testing",
            "type": "code",
            "source": "text_search_test.py",
        })

        # Text search should always work
        result = server.handle_call_tool("memory_search", {
            "query": "text search",
            "type": "text",
            "limit": 10
        })
        assert result.get("isError") is not True

    def test_session_save_without_redis(self, test_config):
        """Test session_save falls back gracefully when Redis unavailable."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", False):
            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            result = server.handle_call_tool("session_save", {
                "project_path": "fallback/project",
                "active_files": ["file.py"],
                "context": {"fallback": True}
            })

            # Should still succeed (fallback to SQLite-based session)
            assert result.get("isError") is not True

    def test_store_without_embeddings(self, test_config):
        """Test memory_store works when embedding provider unavailable."""
        with patch("memory_mcp.server.get_embedding_provider") as mock_get_provider:
            mock_get_provider.return_value = None  # No provider available

            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            # Store should still work (just without vector indexing)
            result = server.handle_call_tool("memory_store", {
                "content": "Content without embeddings",
                "type": "note",
                "source": "no_embed.py",
            })
            assert result.get("isError") is not True

    def test_all_optional_components_unavailable(self, test_config):
        """Test core functionality works with only SQLite and Vault."""
        with patch("memory_mcp.redis_client.REDIS_AVAILABLE", False):
            with patch("memory_mcp.server.get_embedding_provider") as mock_get_provider:
                mock_get_provider.return_value = None  # No provider

                from memory_mcp.server import MemoryMCPServer
                server = MemoryMCPServer(config=test_config)

                # Core operations should still work
                store_result = server.handle_call_tool("memory_store", {
                    "content": "Minimal mode content",
                    "type": "note",
                    "source": "minimal.py",
                })
                assert store_result.get("isError") is not True

                doc_id = json.loads(store_result["content"][0]["text"])["id"]

                recall_result = server.handle_call_tool("memory_recall", {
                    "id": doc_id
                })
                assert recall_result.get("isError") is not True


class TestErrorHandling:
    """Test comprehensive error handling across all endpoints."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_unknown_tool_returns_error(self, mcp_server):
        """Test calling unknown tool returns proper error."""
        result = mcp_server.handle_call_tool("nonexistent_tool", {})

        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_invalid_document_type_handled(self, mcp_server):
        """Test invalid document type is handled gracefully."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content",
            "type": "invalid_type_xyz",
            "source": "test.py"
        })

        # Should either error gracefully or reject
        assert result is not None
        if result.get("isError"):
            assert "type" in result["content"][0]["text"].lower() or "invalid" in result["content"][0]["text"].lower()

    def test_missing_required_fields_handled(self, mcp_server):
        """Test missing required fields return proper error."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content only"
            # Missing type and source
        })

        # Should handle gracefully
        assert result is not None

    def test_recall_nonexistent_document(self, mcp_server):
        """Test recalling nonexistent document returns found=False."""
        result = mcp_server.handle_call_tool("memory_recall", {
            "id": "nonexistent-doc-id-12345"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert data.get("found") is False

    def test_delete_nonexistent_document(self, mcp_server):
        """Test deleting nonexistent document handles gracefully."""
        result = mcp_server.handle_call_tool("memory_delete", {
            "id": "nonexistent-delete-id-12345"
        })

        # Should not crash, may indicate not found
        assert result is not None

    def test_vault_read_nonexistent_file(self, mcp_server):
        """Test reading nonexistent vault file returns found=False."""
        result = mcp_server.handle_call_tool("vault_read", {
            "path": "nonexistent/path/to/file"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert data.get("found") is False

    def test_empty_search_query(self, mcp_server):
        """Test empty search query is handled."""
        result = mcp_server.handle_call_tool("memory_search", {
            "query": "",
            "type": "text"
        })

        # Should handle gracefully (either error or empty results)
        assert result is not None

    def test_content_exceeds_max_size(self, mcp_server):
        """Test content larger than max size is rejected."""
        # Create content larger than 1MB
        large_content = "x" * (1024 * 1024 + 1)  # 1MB + 1 byte

        result = mcp_server.handle_call_tool("memory_store", {
            "content": large_content,
            "type": "note",
            "source": "large.py"
        })

        # Should reject with error about size
        assert result.get("isError") is True
        error_text = result["content"][0]["text"].lower()
        assert "size" in error_text or "bytes" in error_text or "characters" in error_text


class TestConcurrentAccess:
    """Test thread-safety and concurrent access patterns."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_concurrent_stores(self, mcp_server):
        """Test multiple simultaneous store operations don't conflict."""
        results = []
        errors = []

        def store_document(i):
            try:
                result = mcp_server.handle_call_tool("memory_store", {
                    "content": f"Concurrent document {i}",
                    "type": "note",
                    "source": f"concurrent/doc_{i}.py",
                })
                results.append(result)
                return result
            except Exception as e:
                errors.append(str(e))
                return None

        # Run 10 concurrent stores
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(store_document, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        # All should succeed without errors
        assert len(errors) == 0
        assert len(results) == 10
        for result in results:
            assert result.get("isError") is not True

    def test_concurrent_searches(self, mcp_server):
        """Test multiple simultaneous search operations."""
        # Store some searchable content first
        for i in range(5):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Searchable concurrent content {i}",
                "type": "note",
                "source": f"search_content_{i}.py",
            })

        results = []
        errors = []

        def search_documents(query):
            try:
                result = mcp_server.handle_call_tool("memory_search", {
                    "query": query,
                    "type": "text",
                    "limit": 10
                })
                results.append(result)
                return result
            except Exception as e:
                errors.append(str(e))
                return None

        queries = ["searchable", "concurrent", "content", "document", "test"]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search_documents, q) for q in queries]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0
        assert len(results) == 5

    def test_concurrent_mixed_operations(self, mcp_server):
        """Test concurrent store, search, and recall operations."""
        results = []
        errors = []
        stored_ids = []

        def mixed_operation(i):
            try:
                # Store
                store_result = mcp_server.handle_call_tool("memory_store", {
                    "content": f"Mixed operation content {i}",
                    "type": "note",
                    "source": f"mixed_{i}.py",
                })

                if store_result.get("isError") is not True:
                    doc_id = json.loads(store_result["content"][0]["text"])["id"]
                    stored_ids.append(doc_id)

                    # Recall
                    mcp_server.handle_call_tool("memory_recall", {
                        "id": doc_id
                    })

                    # Search
                    mcp_server.handle_call_tool("memory_search", {
                        "query": f"operation {i}",
                        "type": "text"
                    })

                results.append(store_result)
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(5)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0


class TestPerformanceBaseline:
    """Establish performance baselines for API health."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    @pytest.mark.slow
    def test_store_latency_baseline(self, mcp_server):
        """Test memory_store completes within acceptable time."""
        latencies = []

        for i in range(10):
            start = time.perf_counter()
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Performance test content {i}",
                "type": "note",
                "source": f"perf_{i}.py",
            })
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Store should complete within 500ms on average
        assert avg_latency < 500, f"Average store latency {avg_latency:.1f}ms exceeds 500ms"
        # No single operation should take more than 2 seconds
        assert max_latency < 2000, f"Max store latency {max_latency:.1f}ms exceeds 2000ms"

    @pytest.mark.slow
    def test_search_latency_baseline(self, mcp_server):
        """Test memory_search completes within acceptable time."""
        # Store some content first
        for i in range(20):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Search performance test document {i} with various keywords",
                "type": "note",
                "source": f"search_perf_{i}.py",
            })

        latencies = []

        for i in range(10):
            start = time.perf_counter()
            mcp_server.handle_call_tool("memory_search", {
                "query": "performance test",
                "type": "text",
                "limit": 10
            })
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)

        # Search should complete within 200ms on average (text search)
        assert avg_latency < 200, f"Average search latency {avg_latency:.1f}ms exceeds 200ms"


class TestResponseStructure:
    """Validate response structure consistency across all endpoints."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_all_responses_have_content_array(self, mcp_server):
        """Test all tool responses have content array structure."""
        # Store
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Structure test",
            "type": "note",
            "source": "structure.py"
        })
        assert "content" in result
        assert isinstance(result["content"], list)

        # Stats
        result = mcp_server.handle_call_tool("memory_stats", {})
        assert "content" in result
        assert isinstance(result["content"], list)

    def test_all_content_items_have_text(self, mcp_server):
        """Test all content items have text field."""
        tools_and_args = [
            ("memory_stats", {}),
            ("memory_list", {"limit": 5}),
        ]

        for tool_name, args in tools_and_args:
            result = mcp_server.handle_call_tool(tool_name, args)

            if result.get("isError") is not True:
                for item in result["content"]:
                    assert "text" in item

    def test_error_responses_have_isError_true(self, mcp_server):
        """Test error responses properly set isError flag."""
        result = mcp_server.handle_call_tool("unknown_tool", {})

        assert result["isError"] is True


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance for health verification."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_initialize_response_format(self, mcp_server):
        """Test initialize response matches MCP protocol."""
        result = mcp_server.handle_initialize({})

        assert "protocolVersion" in result
        assert "serverInfo" in result
        assert "name" in result["serverInfo"]
        assert "capabilities" in result

    def test_list_tools_returns_all_tools(self, mcp_server):
        """Test list_tools returns all 20 tools (10 core + 5 research + 5 tier)."""
        result = mcp_server.handle_list_tools()

        assert "tools" in result
        assert len(result["tools"]) == 20

        expected_tools = [
            # Core tools
            "memory_store", "memory_search", "memory_recall", "memory_delete",
            "memory_list", "session_save", "session_restore",
            "vault_write", "vault_read", "memory_stats",
            # Research tools
            "research_session_start", "research_session_end",
            "research_transcript_store", "research_capture_store", "research_search",
            # Tier tools
            "search_entities", "search_facts", "code_search",
            "search_function", "search_class"
        ]

        tool_names = [t["name"] for t in result["tools"]]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_tool_schemas_are_valid(self, mcp_server):
        """Test all tool schemas have required fields."""
        result = mcp_server.handle_list_tools()

        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "type" in tool["inputSchema"]
            assert tool["inputSchema"]["type"] == "object"
