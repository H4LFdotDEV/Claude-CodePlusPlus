# test_server_sdk.py
# Comprehensive test suite for Memory MCP Server SDK
# Tests cover: component initialization, tool schemas, tool handlers, error handling

import asyncio
import pytest
import uuid as uuid_module
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from mcp.types import TextContent
from datetime import datetime, timezone

# Mock the MCP components to avoid import errors in test environment
pytest.importorskip("mcp")

from memory_mcp.server_sdk import (
    get_components,
    list_tools,
    call_tool,
    server,
)


# ============================================================================
# CATEGORY 1: Component Initialization (6 tests)
# ============================================================================

class TestComponentInitialization:
    """Test component initialization and lazy loading."""

    def test_get_components_returns_all_four(self):
        """Test get_components returns index, vault, redis, faiss."""
        # Reset global state
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex'):
            with patch('memory_mcp.server_sdk.VaultManager'):
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', False):
                    with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', False):
                        index, vault, redis, faiss = get_components()

                        assert index is not None
                        assert vault is not None
                        assert redis is None
                        assert faiss is None

    def test_get_components_lazy_loading(self):
        """Test get_components initializes only once."""
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex') as mock_index:
            with patch('memory_mcp.server_sdk.VaultManager') as mock_vault:
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', False):
                    with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', False):
                        # First call
                        get_components()
                        first_index_calls = mock_index.call_count

                        # Second call
                        get_components()
                        second_index_calls = mock_index.call_count

                        # Should not reinitialize
                        assert first_index_calls == second_index_calls

    def test_get_components_with_redis_available(self):
        """Test get_components initializes Redis when available."""
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex'):
            with patch('memory_mcp.server_sdk.VaultManager'):
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', True):
                    with patch('memory_mcp.server_sdk.RedisClient') as mock_redis:
                        with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', False):
                            index, vault, redis, faiss = get_components()

                            assert redis is not None
                            mock_redis.assert_called_once()

    def test_get_components_with_faiss_available(self):
        """Test get_components initializes FAISS when available."""
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex'):
            with patch('memory_mcp.server_sdk.VaultManager'):
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', False):
                    with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', True):
                        mock_faiss = MagicMock()
                        mock_faiss.index.ntotal = 1000
                        with patch('memory_mcp.server_sdk.FAISSManager', return_value=mock_faiss):
                            index, vault, redis, faiss = get_components()

                            assert faiss is not None
                            assert faiss.index.ntotal == 1000

    def test_get_components_with_all_available(self):
        """Test get_components with all components available."""
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex'):
            with patch('memory_mcp.server_sdk.VaultManager'):
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', True):
                    with patch('memory_mcp.server_sdk.RedisClient'):
                        with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', True):
                            mock_faiss = MagicMock()
                            mock_faiss.index.ntotal = 500
                            with patch('memory_mcp.server_sdk.FAISSManager', return_value=mock_faiss):
                                index, vault, redis, faiss = get_components()

                                assert index is not None
                                assert vault is not None
                                assert redis is not None
                                assert faiss is not None

    def test_get_components_returns_same_instance(self):
        """Test get_components returns same instance on subsequent calls."""
        import memory_mcp.server_sdk as sdk_module
        sdk_module._index = None
        sdk_module._vault = None
        sdk_module._redis = None
        sdk_module._faiss = None

        with patch('memory_mcp.server_sdk.SQLiteIndex'):
            with patch('memory_mcp.server_sdk.VaultManager'):
                with patch('memory_mcp.server_sdk.REDIS_AVAILABLE', False):
                    with patch('memory_mcp.server_sdk.FAISS_AVAILABLE', False):
                        index1, vault1, _, _ = get_components()
                        index2, vault2, _, _ = get_components()

                        assert index1 is index2
                        assert vault1 is vault2


# ============================================================================
# CATEGORY 2: Tool Schemas (4 tests)
# ============================================================================

class TestToolSchemas:
    """Test tool schema definitions and validation."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """Test list_tools returns all 10 tools."""
        with patch('memory_mcp.server_sdk.get_components'):
            tools = await list_tools()

            assert len(tools) == 10
            tool_names = [t.name for t in tools]
            assert "memory_store" in tool_names
            assert "memory_search" in tool_names
            assert "memory_list" in tool_names
            assert "memory_recall" in tool_names
            assert "memory_delete" in tool_names
            assert "session_save" in tool_names
            assert "session_restore" in tool_names
            assert "vault_write" in tool_names
            assert "vault_read" in tool_names
            assert "memory_stats" in tool_names

    @pytest.mark.asyncio
    async def test_tool_schema_memory_store(self):
        """Test memory_store tool schema is valid."""
        with patch('memory_mcp.server_sdk.get_components'):
            tools = await list_tools()
            store_tool = next(t for t in tools if t.name == "memory_store")

            assert store_tool.description is not None
            assert "required" in store_tool.inputSchema
            assert "content" in store_tool.inputSchema["required"]
            assert "type" in store_tool.inputSchema["required"]
            assert "source" in store_tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_tool_schema_memory_search(self):
        """Test memory_search tool schema is valid."""
        with patch('memory_mcp.server_sdk.get_components'):
            tools = await list_tools()
            search_tool = next(t for t in tools if t.name == "memory_search")

            assert search_tool.description is not None
            assert "query" in search_tool.inputSchema["required"]
            # Should have type and limit as optional
            assert "type" in search_tool.inputSchema["properties"]
            assert "limit" in search_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_tool_schema_properties_exist(self):
        """Test all tools have required schema properties."""
        with patch('memory_mcp.server_sdk.get_components'):
            tools = await list_tools()

            for tool in tools:
                assert hasattr(tool, 'name')
                assert hasattr(tool, 'description')
                assert hasattr(tool, 'inputSchema')
                assert isinstance(tool.inputSchema, dict)
                assert "properties" in tool.inputSchema or tool.inputSchema.get("properties") == {}


# ============================================================================
# CATEGORY 3: Tool Handlers - Memory Tools (20 tests)
# ============================================================================

class TestMemoryStoreHandler:
    """Test memory_store tool handler."""

    @pytest.mark.asyncio
    async def test_store_with_all_fields(self):
        """Test memory_store with all fields populated."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with patch('uuid.uuid4', return_value=uuid_module.UUID('12345678-1234-5678-1234-567812345678')):
                result = await call_tool("memory_store", {
                    "content": "test content",
                    "type": "code",
                    "source": "test_source",
                    "tags": ["tag1", "tag2"],
                    "project": "test_project"
                })

                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                assert "Stored memory" in result[0].text
                assert mock_index.insert.called

    @pytest.mark.asyncio
    async def test_store_with_minimal_fields(self):
        """Test memory_store with only required fields."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_store", {
                "content": "minimal content",
                "type": "note",
                "source": "test"
            })

            assert len(result) == 1
            assert "Stored memory" in result[0].text
            assert mock_index.insert.called

    @pytest.mark.asyncio
    async def test_store_returns_id(self):
        """Test memory_store returns the stored ID."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        test_id = "test-id-123"
        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with patch('uuid.uuid4', return_value=uuid_module.UUID('12345678-1234-5678-1234-567812345678')):
                result = await call_tool("memory_store", {
                    "content": "test",
                    "type": "reference",
                    "source": "test"
                })

                assert "ID:" in result[0].text

    @pytest.mark.asyncio
    async def test_store_with_code_type(self):
        """Test memory_store with code document type."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_store", {
                "content": "def test(): pass",
                "type": "code",
                "source": "github"
            })

            assert "Stored memory" in result[0].text

    @pytest.mark.asyncio
    async def test_store_with_reference_type(self):
        """Test memory_store with reference document type."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_store", {
                "content": "reference content",
                "type": "reference",
                "source": "docs"
            })

            assert "Stored memory" in result[0].text

    @pytest.mark.asyncio
    async def test_store_with_conversation_type(self):
        """Test memory_store with conversation document type."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_store", {
                "content": "conversation content",
                "type": "conversation",
                "source": "claude"
            })

            assert "Stored memory" in result[0].text


class TestMemorySearchHandler:
    """Test memory_search tool handler."""

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        """Test memory_search with search results."""
        mock_doc = MagicMock()
        mock_doc.doc_type = "note"
        mock_doc.source = "test_source"
        mock_doc.content = "This is a test document with more content here"

        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = [mock_doc]
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_search", {
                "query": "test query",
                "limit": 10
            })

            assert len(result) == 1
            assert "Found 1 results" in result[0].text
            assert mock_index.search_fulltext.called

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test memory_search with no results."""
        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = []
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_search", {
                "query": "nonexistent"
            })

            assert len(result) == 1
            assert "No results" in result[0].text

    @pytest.mark.asyncio
    async def test_search_with_custom_limit(self):
        """Test memory_search respects limit parameter."""
        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = []
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            await call_tool("memory_search", {
                "query": "test",
                "limit": 5
            })

            # Verify limit was passed
            call_args = mock_index.search_fulltext.call_args
            assert call_args[1].get("limit") == 5 or call_args[0][1] == 5

    @pytest.mark.asyncio
    async def test_search_with_multiple_results(self):
        """Test memory_search with multiple results."""
        mock_docs = [
            MagicMock(doc_type="note", source="src1", content="content1"),
            MagicMock(doc_type="code", source="src2", content="content2"),
            MagicMock(doc_type="reference", source="src3", content="content3"),
        ]

        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = mock_docs
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_search", {"query": "test"})

            assert "Found 3 results" in result[0].text

    @pytest.mark.asyncio
    async def test_search_with_type_parameter(self):
        """Test memory_search passes search type."""
        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = []
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            await call_tool("memory_search", {
                "query": "test",
                "type": "semantic"
            })

            # Should still call search_fulltext
            assert mock_index.search_fulltext.called


class TestMemoryListHandler:
    """Test memory_list tool handler."""

    @pytest.mark.asyncio
    async def test_list_with_results(self):
        """Test memory_list with memories available."""
        mock_doc = MagicMock()
        mock_doc.doc_type = "conversation"
        mock_doc.source = "claude"
        mock_doc.content = "This is a conversation example"

        mock_index = MagicMock()
        mock_index.get_recent.return_value = [mock_doc]
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_list", {})

            assert len(result) == 1
            assert "Recent 1 memories" in result[0].text

    @pytest.mark.asyncio
    async def test_list_empty_results(self):
        """Test memory_list with no memories."""
        mock_index = MagicMock()
        mock_index.get_recent.return_value = []
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_list", {})

            assert len(result) == 1
            assert "No memories" in result[0].text

    @pytest.mark.asyncio
    async def test_list_default_limit(self):
        """Test memory_list uses default limit."""
        mock_index = MagicMock()
        mock_index.get_recent.return_value = []
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            await call_tool("memory_list", {})

            # Verify default limit was used
            call_args = mock_index.get_recent.call_args
            assert call_args[1].get("limit") == 20 or call_args[0][0] == 20


class TestMemoryRecallHandler:
    """Test memory_recall tool handler."""

    @pytest.mark.asyncio
    async def test_recall_found(self):
        """Test memory_recall when memory is found."""
        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.doc_type = "code"
        mock_doc.source = "github"
        mock_doc.created_at = "2026-01-21T00:00:00Z"
        mock_doc.tags = ["python", "test"]
        mock_doc.project = "test-project"
        mock_doc.content = "def test_function(): pass"

        mock_index = MagicMock()
        mock_index.get.return_value = mock_doc
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_recall", {"id": "doc-123"})

            assert len(result) == 1
            assert "Memory doc-123" in result[0].text
            assert "code" in result[0].text
            assert "github" in result[0].text

    @pytest.mark.asyncio
    async def test_recall_not_found(self):
        """Test memory_recall when memory not found."""
        mock_index = MagicMock()
        mock_index.get.return_value = None
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_recall", {"id": "nonexistent"})

            assert len(result) == 1
            assert "not found" in result[0].text


class TestMemoryDeleteHandler:
    """Test memory_delete tool handler."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test memory_delete when deletion succeeds."""
        mock_index = MagicMock()
        mock_index.delete.return_value = True
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_delete", {"id": "doc-123"})

            assert len(result) == 1
            assert "Deleted memory" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test memory_delete when memory not found."""
        mock_index = MagicMock()
        mock_index.delete.return_value = False
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_delete", {"id": "nonexistent"})

            assert len(result) == 1
            assert "not found" in result[0].text


# ============================================================================
# CATEGORY 4: Tool Handlers - Session Tools (8 tests)
# ============================================================================

class TestSessionSaveHandler:
    """Test session_save tool handler."""

    @pytest.mark.asyncio
    async def test_save_with_redis(self):
        """Test session_save when Redis is available."""
        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            result = await call_tool("session_save", {
                "project_path": "home/user/project",
                "active_files": ["file1.py", "file2.py"],
                "context": {"key": "value"}
            })

            assert len(result) == 1
            assert "Session saved" in result[0].text
            assert mock_redis.save_session.called

    @pytest.mark.asyncio
    async def test_save_without_redis(self):
        """Test session_save when Redis not available."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("session_save", {
                "project_path": "home/user/project"
            })

            assert len(result) == 1
            assert "requires Redis" in result[0].text

    @pytest.mark.asyncio
    async def test_save_with_minimal_fields(self):
        """Test session_save with only required fields."""
        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            result = await call_tool("session_save", {
                "project_path": "path"
            })

            assert len(result) == 1
            assert "Session saved" in result[0].text


class TestSessionRestoreHandler:
    """Test session_restore tool handler."""

    @pytest.mark.asyncio
    async def test_restore_with_session_id(self):
        """Test session_restore with valid session ID."""
        mock_state = MagicMock()
        mock_state.session_id = "session-123"
        mock_state.project_path = "/home/user/project"
        mock_state.active_files = ["file1.py"]
        mock_state.context = {}

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()
        mock_redis.get_session.return_value = mock_state

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            result = await call_tool("session_restore", {
                "session_id": "session-123"
            })

            assert len(result) == 1
            assert "Restored session" in result[0].text
            assert mock_redis.get_session.called

    @pytest.mark.asyncio
    async def test_restore_without_redis(self):
        """Test session_restore when Redis not available."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("session_restore", {})

            assert len(result) == 1
            assert "requires Redis" in result[0].text

    @pytest.mark.asyncio
    async def test_restore_not_found(self):
        """Test session_restore when session not found."""
        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()
        mock_redis.get_session.return_value = None

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            result = await call_tool("session_restore", {
                "session_id": "nonexistent"
            })

            assert len(result) == 1
            assert "No session found" in result[0].text


# ============================================================================
# CATEGORY 5: Tool Handlers - Vault Tools (8 tests)
# ============================================================================

class TestVaultWriteHandler:
    """Test vault_write tool handler."""

    @pytest.mark.asyncio
    async def test_write_with_all_params(self):
        """Test vault_write with all parameters."""
        mock_note = MagicMock()
        mock_note.path = "code/test_file"

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.write_note.return_value = mock_note

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("vault_write", {
                "path": "test_file",
                "content": "# Test\n\nContent here",
                "folder": "code",
                "tags": ["python", "test"]
            })

            assert len(result) == 1
            assert "Written to vault" in result[0].text
            assert mock_vault.write_note.called

    @pytest.mark.asyncio
    async def test_write_minimal_params(self):
        """Test vault_write with minimal parameters."""
        mock_note = MagicMock()
        mock_note.path = "notes/test"

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.write_note.return_value = mock_note

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("vault_write", {
                "path": "test",
                "content": "Simple content"
            })

            assert len(result) == 1
            assert "Written to vault" in result[0].text


class TestVaultReadHandler:
    """Test vault_read tool handler."""

    @pytest.mark.asyncio
    async def test_read_found(self):
        """Test vault_read when note is found."""
        mock_note = MagicMock()
        mock_note.title = "Test Note"
        mock_note.path = "code/test"
        mock_note.tags = ["test"]
        mock_note.created_at = "2026-01-21T00:00:00Z"
        mock_note.modified_at = "2026-01-21T10:00:00Z"
        mock_note.content = "# Test\n\nContent"

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.read_note.return_value = mock_note

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("vault_read", {"path": "code/test"})

            assert len(result) == 1
            assert "Test Note" in result[0].text
            assert mock_vault.read_note.called

    @pytest.mark.asyncio
    async def test_read_not_found(self):
        """Test vault_read when note not found."""
        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.read_note.return_value = None

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("vault_read", {"path": "nonexistent"})

            assert len(result) == 1
            assert "not found" in result[0].text


# ============================================================================
# CATEGORY 6: Tool Handlers - Stats & Error Handling (10 tests)
# ============================================================================

class TestMemoryStatsHandler:
    """Test memory_stats tool handler."""

    @pytest.mark.asyncio
    async def test_stats_all_components(self):
        """Test memory_stats with all components available."""
        mock_index = MagicMock()
        mock_index.get_stats.return_value = {
            'total_documents': 100,
            'by_type': {'code': 50, 'note': 30, 'conversation': 20}
        }
        mock_vault = MagicMock()
        mock_vault.get_stats.return_value = {'total_notes': 50}
        mock_faiss = MagicMock()
        mock_faiss.index.ntotal = 200
        mock_redis = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, mock_faiss)):
            result = await call_tool("memory_stats", {})

            assert len(result) == 1
            assert "Memory Statistics" in result[0].text
            assert "100" in result[0].text  # total documents
            assert "200" in result[0].text  # FAISS vectors
            assert "available" in result[0].text  # Redis

    @pytest.mark.asyncio
    async def test_stats_minimal_components(self):
        """Test memory_stats with minimal components."""
        mock_index = MagicMock()
        mock_index.get_stats.return_value = {'total_documents': 10}
        mock_vault = MagicMock()
        mock_vault.get_stats.return_value = {'total_notes': 5}

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_stats", {})

            assert len(result) == 1
            assert "Memory Statistics" in result[0].text
            assert "N/A" in result[0].text  # FAISS and Redis


class TestUnknownToolHandler:
    """Test handling of unknown tool names."""

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Test call_tool with unknown tool name."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test call_tool with invalid tool name."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("invalid", {})

            assert len(result) == 1
            assert "Unknown" in result[0].text


class TestErrorHandling:
    """Test error handling in tool handlers."""

    @pytest.mark.asyncio
    async def test_store_missing_required_field(self):
        """Test memory_store with missing required field."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Missing "source" field
            with pytest.raises(KeyError):
                await call_tool("memory_store", {
                    "content": "test",
                    "type": "note"
                })

    @pytest.mark.asyncio
    async def test_search_missing_query(self):
        """Test memory_search with missing query."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with pytest.raises(KeyError):
                await call_tool("memory_search", {})

    @pytest.mark.asyncio
    async def test_recall_missing_id(self):
        """Test memory_recall with missing ID."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with pytest.raises(KeyError):
                await call_tool("memory_recall", {})

    @pytest.mark.asyncio
    async def test_vault_write_missing_content(self):
        """Test vault_write with missing content."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with pytest.raises(KeyError):
                await call_tool("vault_write", {
                    "path": "test"
                })

    @pytest.mark.asyncio
    async def test_vault_read_missing_path(self):
        """Test vault_read with missing path."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with pytest.raises(KeyError):
                await call_tool("vault_read", {})

    @pytest.mark.asyncio
    async def test_delete_missing_id(self):
        """Test memory_delete with missing ID."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            with pytest.raises(KeyError):
                await call_tool("memory_delete", {})


# ============================================================================
# CATEGORY 7: Integration Tests (5 tests)
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_store_and_search_workflow(self):
        """Test complete store and search workflow."""
        mock_stored_doc = MagicMock()
        mock_stored_doc.doc_type = "code"
        mock_stored_doc.source = "test"
        mock_stored_doc.content = "stored content"

        mock_index = MagicMock()
        mock_index.insert = MagicMock()
        mock_index.search_fulltext.return_value = [mock_stored_doc]
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Store
            store_result = await call_tool("memory_store", {
                "content": "stored content",
                "type": "code",
                "source": "test"
            })
            assert "Stored memory" in store_result[0].text

            # Search
            search_result = await call_tool("memory_search", {
                "query": "stored"
            })
            assert "Found" in search_result[0].text

    @pytest.mark.asyncio
    async def test_session_save_and_restore_workflow(self):
        """Test complete session save and restore workflow."""
        mock_state = MagicMock()
        mock_state.session_id = "session-123"
        mock_state.project_path = "/project"
        mock_state.active_files = []
        mock_state.context = {}

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()
        mock_redis.get_session.return_value = mock_state

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            # Save
            save_result = await call_tool("session_save", {
                "project_path": "project"
            })
            assert "Session saved" in save_result[0].text

            # Restore
            restore_result = await call_tool("session_restore", {
                "session_id": "session-123"
            })
            assert "Restored" in restore_result[0].text

    @pytest.mark.asyncio
    async def test_vault_write_and_read_workflow(self):
        """Test complete vault write and read workflow."""
        mock_note_write = MagicMock()
        mock_note_write.path = "code/test"

        mock_note_read = MagicMock()
        mock_note_read.title = "Test"
        mock_note_read.path = "code/test"
        mock_note_read.tags = []
        mock_note_read.created_at = "2026-01-21"
        mock_note_read.modified_at = "2026-01-21"
        mock_note_read.content = "# Test\nContent"

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.write_note.return_value = mock_note_write
        mock_vault.read_note.return_value = mock_note_read

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Write
            write_result = await call_tool("vault_write", {
                "path": "test",
                "content": "# Test\nContent",
                "folder": "code"
            })
            assert "Written" in write_result[0].text

            # Read
            read_result = await call_tool("vault_read", {
                "path": "code/test"
            })
            assert "Test" in read_result[0].text

    @pytest.mark.asyncio
    async def test_multiple_concurrent_tool_calls(self):
        """Test multiple concurrent tool calls."""
        mock_index = MagicMock()
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Run multiple tool calls concurrently
            tasks = [
                call_tool("memory_list", {}),
                call_tool("memory_stats", {}),
                call_tool("memory_search", {"query": "test"})
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            assert all(len(r) > 0 for r in results)
            assert all(isinstance(r[0], TextContent) for r in results)

    @pytest.mark.asyncio
    async def test_store_search_recall_workflow(self):
        """Test complete store -> search -> recall workflow."""
        mock_stored_doc = MagicMock()
        mock_stored_doc.id = "doc-123"
        mock_stored_doc.doc_type = "code"
        mock_stored_doc.source = "test"
        mock_stored_doc.content = "def test(): pass"
        mock_stored_doc.created_at = "2026-01-21T00:00:00Z"
        mock_stored_doc.tags = ["python"]
        mock_stored_doc.project = "test"

        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = [mock_stored_doc]
        mock_index.get.return_value = mock_stored_doc
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Store
            store_result = await call_tool("memory_store", {
                "content": "def test(): pass",
                "type": "code",
                "source": "test"
            })
            assert "Stored" in store_result[0].text

            # Search
            search_result = await call_tool("memory_search", {
                "query": "test"
            })
            assert "Found" in search_result[0].text

            # Recall
            recall_result = await call_tool("memory_recall", {
                "id": "doc-123"
            })
            assert "Memory doc-123" in recall_result[0].text

    @pytest.mark.asyncio
    async def test_delete_workflow(self):
        """Test delete workflow."""
        mock_index = MagicMock()
        mock_index.delete.return_value = True
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_delete", {"id": "doc-123"})

            assert "Deleted" in result[0].text
            assert mock_index.delete.called

    @pytest.mark.asyncio
    async def test_complete_vault_workflow(self):
        """Test complete vault write -> read workflow."""
        mock_note_write = MagicMock()
        mock_note_write.path = "code/test"

        mock_note_read = MagicMock()
        mock_note_read.title = "Test Note"
        mock_note_read.path = "code/test"
        mock_note_read.tags = ["python", "test"]
        mock_note_read.created_at = "2026-01-21"
        mock_note_read.modified_at = "2026-01-21"
        mock_note_read.content = "# Test\n\nContent"

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_vault.write_note.return_value = mock_note_write
        mock_vault.read_note.return_value = mock_note_read

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Write with all params
            write_result = await call_tool("vault_write", {
                "path": "test",
                "content": "# Test\n\nContent",
                "folder": "code",
                "tags": ["python", "test"]
            })
            assert "Written" in write_result[0].text

            # Read
            read_result = await call_tool("vault_read", {
                "path": "code/test"
            })
            assert "Test Note" in read_result[0].text
            assert "python" in read_result[0].text

    @pytest.mark.asyncio
    async def test_stats_with_different_document_types(self):
        """Test memory_stats with different document types."""
        mock_index = MagicMock()
        mock_index.get_stats.return_value = {
            'total_documents': 150,
            'by_type': {'code': 80, 'note': 40, 'conversation': 20, 'reference': 10}
        }
        mock_vault = MagicMock()
        mock_vault.get_stats.return_value = {'total_notes': 75}

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_stats", {})

            assert "Memory Statistics" in result[0].text
            assert "150" in result[0].text

    @pytest.mark.asyncio
    async def test_stress_sequential_tool_calls(self):
        """Test sequential execution of multiple tool calls."""
        mock_index = MagicMock()
        mock_index.search_fulltext.return_value = []
        mock_index.get_recent.return_value = []
        mock_vault = MagicMock()
        mock_vault.get_stats.return_value = {'total_notes': 10}

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            # Execute multiple calls in sequence
            for i in range(5):
                result = await call_tool("memory_search", {"query": f"test_{i}"})
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_memory_recall_with_empty_tags(self):
        """Test memory_recall displays 'none' when tags are empty."""
        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.doc_type = "note"
        mock_doc.source = "test"
        mock_doc.created_at = "2026-01-21"
        mock_doc.tags = []
        mock_doc.project = None
        mock_doc.content = "content"

        mock_index = MagicMock()
        mock_index.get.return_value = mock_doc
        mock_vault = MagicMock()

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, None, None)):
            result = await call_tool("memory_recall", {"id": "doc-123"})

            assert "none" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_session_with_empty_fields(self):
        """Test session handlers with empty optional fields."""
        mock_state = MagicMock()
        mock_state.session_id = "session-123"
        mock_state.project_path = "/project"
        mock_state.active_files = []
        mock_state.context = {}

        mock_index = MagicMock()
        mock_vault = MagicMock()
        mock_redis = MagicMock()
        mock_redis.get_session.return_value = mock_state

        with patch('memory_mcp.server_sdk.get_components', return_value=(mock_index, mock_vault, mock_redis, None)):
            result = await call_tool("session_restore", {
                "session_id": "session-123"
            })

            assert "session-123" in result[0].text
            assert "none" in result[0].text.lower()
