# test_mcp_protocol.py
# Tests for MCP (Model Context Protocol) JSON-RPC communication
#
# Tests the MCP server's protocol handling, including:
# - JSON-RPC message format
# - Request/response handling
# - Error responses
# - Tool dispatch

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestMCPProtocolBasics:
    """Test basic MCP protocol handling."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for protocol testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_initialize_request(self, mcp_server):
        """Test MCP initialize request handling."""
        result = mcp_server.handle_initialize({
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })

        assert "protocolVersion" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "claude-code-pp-memory"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]

    def test_initialize_echoes_client_version(self, mcp_server):
        """Test that initialize echoes client's protocol version."""
        result = mcp_server.handle_initialize({
            "protocolVersion": "2025-01-01"
        })

        assert result["protocolVersion"] == "2025-01-01"

    def test_list_tools(self, mcp_server):
        """Test MCP tools/list request."""
        result = mcp_server.handle_list_tools()

        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) > 0

        # Verify expected tools are present
        tool_names = [t["name"] for t in result["tools"]]
        expected_tools = [
            "memory_store",
            "memory_search",
            "memory_recall",
            "memory_delete",
            "memory_list",
            "session_save",
            "session_restore",
            "vault_write",
            "vault_read",
            "memory_stats"
        ]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_tool_schema_structure(self, mcp_server):
        """Test that tool schemas have correct structure."""
        result = mcp_server.handle_list_tools()

        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "type" in tool["inputSchema"]
            assert tool["inputSchema"]["type"] == "object"


class TestMCPToolCalling:
    """Test MCP tool invocation."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for tool testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_call_tool_success(self, mcp_server):
        """Test successful tool call."""
        result = mcp_server.handle_call_tool("memory_stats", {})

        assert "content" in result
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"
        assert "isError" not in result or result["isError"] is not True

        # Parse response JSON
        response_data = json.loads(result["content"][0]["text"])
        assert "sqlite_count" in response_data

    def test_call_unknown_tool(self, mcp_server):
        """Test calling an unknown tool."""
        result = mcp_server.handle_call_tool("unknown_tool", {})

        assert "isError" in result
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_call_tool_validation_error(self, mcp_server):
        """Test tool call with validation error."""
        # memory_store requires content, type, source
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "test"
            # Missing required 'type' and 'source'
        })

        # Should return an error
        assert "isError" in result
        assert result["isError"] is True
        assert "Validation error" in result["content"][0]["text"]

    def test_call_tool_with_valid_args(self, mcp_server):
        """Test tool call with all required arguments."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Test content for protocol test",
            "type": "note",
            "source": "protocol-test.md"
        })

        assert "isError" not in result or result["isError"] is not True
        response_data = json.loads(result["content"][0]["text"])
        assert "id" in response_data
        assert response_data["stored"] is True


class TestMCPJsonRpcFormat:
    """Test JSON-RPC message formatting."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for JSON-RPC testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_create_response_format(self, mcp_server):
        """Test response message format."""
        response = mcp_server._create_response({"test": "data"}, 42)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 42
        assert response["result"] == {"test": "data"}

    def test_create_error_format(self, mcp_server):
        """Test error message format."""
        error = mcp_server._create_error(-32600, "Invalid Request", 42)

        assert error["jsonrpc"] == "2.0"
        assert error["id"] == 42
        assert "error" in error
        assert error["error"]["code"] == -32600
        assert error["error"]["message"] == "Invalid Request"

    def test_handle_request_initialize(self, mcp_server):
        """Test _handle_request for initialize method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "serverInfo" in response["result"]

    def test_handle_request_tools_list(self, mcp_server):
        """Test _handle_request for tools/list method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]

    def test_handle_request_tools_call(self, mcp_server):
        """Test _handle_request for tools/call method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "memory_stats",
                "arguments": {}
            }
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert "content" in response["result"]

    def test_handle_request_unknown_method(self, mcp_server):
        """Test _handle_request for unknown method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "unknown/method",
            "params": {}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found

    def test_handle_request_resources_list(self, mcp_server):
        """Test _handle_request for resources/list method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/list",
            "params": {}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        assert "resources" in response["result"]
        assert response["result"]["resources"] == []

    def test_handle_request_resources_read(self, mcp_server):
        """Test _handle_request for resources/read method."""
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "test://resource"}
        })

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 6
        assert "error" in response
        assert response["error"]["code"] == -32602  # Invalid params (resource not found)


class TestMCPNotifications:
    """Test MCP notification handling."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for notification testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_handle_initialized_notification(self, mcp_server):
        """Test handling notifications/initialized."""
        # Notifications should not raise errors
        mcp_server._handle_notification({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        # No assertion needed - just verify no exception

    def test_handle_cancelled_notification(self, mcp_server):
        """Test handling notifications/cancelled."""
        mcp_server._handle_notification({
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 123}
        })
        # No assertion needed - just verify no exception

    def test_handle_unknown_notification(self, mcp_server):
        """Test handling unknown notifications."""
        # Unknown notifications should be ignored
        mcp_server._handle_notification({
            "jsonrpc": "2.0",
            "method": "unknown/notification"
        })
        # No assertion needed - just verify no exception


class TestMCPToolDispatch:
    """Test the tool dispatch mechanism."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for dispatch testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_dispatch_to_memory_handler(self, mcp_server):
        """Test dispatch to MemoryHandler methods."""
        # Store
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "Dispatch test",
            "type": "note",
            "source": "dispatch.md"
        })
        assert result.get("isError") is not True

        # Search
        result = mcp_server.handle_call_tool("memory_search", {
            "query": "Dispatch",
            "type": "text"
        })
        assert result.get("isError") is not True

        # Recall
        result = mcp_server.handle_call_tool("memory_recall", {
            "id": "nonexistent"
        })
        assert result.get("isError") is not True

        # Delete
        result = mcp_server.handle_call_tool("memory_delete", {
            "id": "nonexistent"
        })
        assert result.get("isError") is not True

        # List
        result = mcp_server.handle_call_tool("memory_list", {
            "limit": 5
        })
        assert result.get("isError") is not True

    def test_dispatch_to_session_handler(self, mcp_server):
        """Test dispatch to SessionHandler methods."""
        # Save
        result = mcp_server.handle_call_tool("session_save", {
            "project_path": "/test/dispatch",
            "active_files": []
        })
        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        session_id = data["session_id"]

        # Restore
        result = mcp_server.handle_call_tool("session_restore", {
            "session_id": session_id
        })
        assert result.get("isError") is not True

    def test_dispatch_to_vault_handler(self, mcp_server):
        """Test dispatch to VaultHandler methods."""
        # Write
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "dispatch/test",
            "content": "Vault dispatch test",
            "folder": "notes"
        })
        assert result.get("isError") is not True

        # Read
        result = mcp_server.handle_call_tool("vault_read", {
            "path": "notes/dispatch/test"
        })
        assert result.get("isError") is not True

    def test_dispatch_to_stats_handler(self, mcp_server):
        """Test dispatch to StatsHandler."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        assert result.get("isError") is not True

        data = json.loads(result["content"][0]["text"])
        assert "sqlite_count" in data
        assert "components" in data
        assert "health" in data


class TestMCPSessionSync:
    """Test session ID synchronization."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for session sync testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_session_id_syncs_on_restore(self, mcp_server):
        """Test that session_id syncs back to server on restore."""
        # Save with initial session
        save_result = mcp_server.handle_call_tool("session_save", {
            "project_path": "/test/sync",
            "active_files": []
        })
        save_data = json.loads(save_result["content"][0]["text"])
        original_session_id = save_data["session_id"]

        # The server's session ID should match
        assert mcp_server._session_id == original_session_id

        # Restore the session (session ID should stay the same or update correctly)
        restore_result = mcp_server.handle_call_tool("session_restore", {
            "session_id": original_session_id
        })
        restore_data = json.loads(restore_result["content"][0]["text"])

        if restore_data.get("found"):
            assert mcp_server._session_id == original_session_id
