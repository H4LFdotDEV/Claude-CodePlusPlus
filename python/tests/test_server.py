# test_server.py
# Tests for Memory MCP Server

import pytest
import json
from unittest.mock import MagicMock, patch


class TestMemoryMCPServer:
    """Tests for MemoryMCPServer class."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_server_creation(self, mcp_server):
        """Test MCP server is created properly."""
        assert mcp_server is not None
        assert mcp_server.sqlite is not None
        assert mcp_server.vault is not None

    def test_handle_initialize(self, mcp_server):
        """Test initialize request handling."""
        result = mcp_server.handle_initialize({})
        assert result["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "claude-code-pp-memory"

    def test_handle_list_tools(self, mcp_server):
        """Test list_tools request handling."""
        result = mcp_server.handle_list_tools()
        assert "tools" in result
        tools = result["tools"]
        assert len(tools) == 10

        tool_names = [t["name"] for t in tools]
        assert "memory_store" in tool_names
        assert "memory_search" in tool_names
        assert "memory_recall" in tool_names
        assert "memory_delete" in tool_names
        assert "memory_list" in tool_names
        assert "session_save" in tool_names
        assert "session_restore" in tool_names
        assert "vault_write" in tool_names
        assert "vault_read" in tool_names
        assert "memory_stats" in tool_names

    def test_handle_unknown_tool(self, mcp_server):
        """Test handling unknown tool."""
        result = mcp_server.handle_call_tool("unknown_tool", {})
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_memory_store_tool(self, mcp_server):
        """Test memory_store tool."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Test content for storage",
            "type": "note",
            "source": "test/source.py",
            "tags": ["test", "sample"],
            "project": "test-project"
        })
        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "id" in data

    def test_memory_recall_tool(self, mcp_server):
        """Test memory_recall tool."""
        # First store something
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "Content to recall",
            "type": "note",
            "source": "test.py",
        })
        stored_data = json.loads(store_result["content"][0]["text"])
        doc_id = stored_data["id"]

        # Then recall it
        result = mcp_server.handle_call_tool("memory_recall", {
            "id": doc_id
        })
        assert result.get("isError") is not True

    def test_memory_recall_not_found(self, mcp_server):
        """Test memory_recall with nonexistent ID."""
        result = mcp_server.handle_call_tool("memory_recall", {
            "id": "nonexistent-id"
        })
        data = json.loads(result["content"][0]["text"])
        assert data.get("found") is False

    def test_memory_search_tool(self, mcp_server):
        """Test memory_search tool."""
        # Store some documents
        mcp_server.handle_call_tool("memory_store", {
            "content": "Python programming guide",
            "type": "code",
            "source": "python.py",
        })

        result = mcp_server.handle_call_tool("memory_search", {
            "query": "python",
            "type": "text",
            "limit": 10
        })
        assert result.get("isError") is not True

    def test_memory_delete_tool(self, mcp_server):
        """Test memory_delete tool."""
        # Store then delete
        store_result = mcp_server.handle_call_tool("memory_store", {
            "content": "To be deleted",
            "type": "note",
            "source": "delete.py",
        })
        stored_data = json.loads(store_result["content"][0]["text"])
        doc_id = stored_data["id"]

        result = mcp_server.handle_call_tool("memory_delete", {
            "id": doc_id
        })
        assert result.get("isError") is not True

    def test_memory_list_tool(self, mcp_server):
        """Test memory_list tool."""
        # Store some documents
        for i in range(3):
            mcp_server.handle_call_tool("memory_store", {
                "content": f"Document {i}",
                "type": "note",
                "source": f"doc{i}.py",
            })

        result = mcp_server.handle_call_tool("memory_list", {
            "limit": 10,
            "type": "note"
        })
        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "documents" in data
        assert "count" in data

    def test_vault_write_tool(self, mcp_server):
        """Test vault_write tool."""
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "test-note",
            "content": "# Test Note\n\nContent here.",
            "folder": "notes",
            "tags": ["test"]
        })
        assert result.get("isError") is not True

    def test_vault_read_tool(self, mcp_server):
        """Test vault_read tool."""
        # Write first
        mcp_server.handle_call_tool("vault_write", {
            "path": "read-test",
            "content": "Content to read",
        })

        result = mcp_server.handle_call_tool("vault_read", {
            "path": "read-test"
        })
        assert result.get("isError") is not True

    def test_vault_read_not_found(self, mcp_server):
        """Test vault_read with nonexistent path."""
        result = mcp_server.handle_call_tool("vault_read", {
            "path": "nonexistent-note"
        })
        data = json.loads(result["content"][0]["text"])
        assert data.get("found") is False

    def test_memory_stats_tool(self, mcp_server):
        """Test memory_stats tool."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert "sqlite_count" in data


class TestMCPProtocol:
    """Tests for MCP protocol handling."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_create_response(self, mcp_server):
        """Test creating MCP response."""
        response = mcp_server._create_response({"key": "value"}, 123)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 123
        assert response["result"] == {"key": "value"}

    def test_create_error(self, mcp_server):
        """Test creating MCP error response."""
        response = mcp_server._create_error(-32600, "Invalid Request", 456)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 456
        assert response["error"]["code"] == -32600
        assert response["error"]["message"] == "Invalid Request"


class TestSessionManagement:
    """Tests for session management tools."""

    @pytest.fixture
    def mcp_server(self, test_config, mock_redis):
        """Create an MCP server with mocked Redis."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", True):
            with patch("memory_mcp.server.RedisClient") as MockRedis:
                MockRedis.return_value = MagicMock()
                MockRedis.return_value.connect.return_value = True
                from memory_mcp.server import MemoryMCPServer
                server = MemoryMCPServer(config=test_config)
                server.redis = MockRedis.return_value
                return server

    def test_session_save_without_redis(self, test_config):
        """Test session_save gracefully handles missing Redis."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", False):
            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            result = server.handle_call_tool("session_save", {
                "project_path": "test/project",
                "active_files": ["file.py"],
                "context": {}
            })
            # Should still work, just without Redis caching
            assert result.get("isError") is not True


class TestToolInputSchema:
    """Tests for tool input schema validation."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_memory_store_schema(self, mcp_server):
        """Test memory_store input schema."""
        tools = mcp_server.handle_list_tools()["tools"]
        store_tool = next(t for t in tools if t["name"] == "memory_store")

        schema = store_tool["inputSchema"]
        assert schema["type"] == "object"
        assert "content" in schema["properties"]
        assert "type" in schema["properties"]
        assert "source" in schema["properties"]
        assert "content" in schema["required"]
        assert "type" in schema["required"]
        assert "source" in schema["required"]

    def test_memory_search_schema(self, mcp_server):
        """Test memory_search input schema."""
        tools = mcp_server.handle_list_tools()["tools"]
        search_tool = next(t for t in tools if t["name"] == "memory_search")

        schema = search_tool["inputSchema"]
        assert "query" in schema["properties"]
        assert "query" in schema["required"]
