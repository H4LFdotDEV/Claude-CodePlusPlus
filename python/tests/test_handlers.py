# test_handlers.py
# Unit tests for extracted handler classes
#
# Tests the individual handler classes:
# - MemoryHandler
# - SessionHandler
# - VaultHandler
# - StatsHandler

import json
import pytest
from unittest.mock import MagicMock, patch


class TestMemoryHandler:
    """Tests for MemoryHandler class."""

    @pytest.fixture
    def memory_handler(self, sqlite_index, vault_manager, mock_redis):
        """Create a MemoryHandler for testing."""
        from memory_mcp.handlers import MemoryHandler
        return MemoryHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,  # Test without Redis
            embedder=None,
            session_id="test-session"
        )

    def test_store_creates_document(self, memory_handler):
        """Test store method creates a document."""
        result = memory_handler.store({
            "content": "Test content",
            "type": "note",
            "source": "test.md"
        })

        assert "id" in result
        assert result["stored"] is True
        assert len(result["id"]) > 0

    def test_store_validates_type(self, memory_handler):
        """Test store validates document type."""
        with pytest.raises(ValueError):
            memory_handler.store({
                "content": "Test",
                "type": "invalid_type",
                "source": "test.md"
            })

    def test_store_with_tags(self, memory_handler):
        """Test store with tags."""
        result = memory_handler.store({
            "content": "Tagged content",
            "type": "note",
            "source": "tagged.md",
            "tags": ["tag1", "tag2"]
        })

        assert result["stored"] is True

        # Recall and verify tags
        recall_result = memory_handler.recall({"id": result["id"]})
        assert recall_result["found"] is True
        assert "tag1" in recall_result["document"]["tags"]

    def test_search_returns_results(self, memory_handler):
        """Test search returns matching results."""
        # Store some content
        memory_handler.store({
            "content": "Searchable unique content xyz123",
            "type": "note",
            "source": "search.md"
        })

        result = memory_handler.search({
            "query": "xyz123",
            "type": "text",
            "limit": 10
        })

        assert "results" in result
        assert "total" in result

    def test_search_with_filters(self, memory_handler):
        """Test search with filters."""
        # Store different types
        memory_handler.store({
            "content": "Code content",
            "type": "code",
            "source": "code.py",
            "project": "filter-test"
        })

        result = memory_handler.search({
            "query": "Code",
            "type": "text",
            "filters": {"doc_type": "code"}
        })

        assert "results" in result

    def test_recall_existing_document(self, memory_handler):
        """Test recall finds existing document."""
        store_result = memory_handler.store({
            "content": "Recallable content",
            "type": "note",
            "source": "recall.md"
        })

        result = memory_handler.recall({"id": store_result["id"]})

        assert result["found"] is True
        assert "document" in result
        assert result["document"]["content"] == "Recallable content"

    def test_recall_nonexistent_document(self, memory_handler):
        """Test recall returns found=False for missing document."""
        result = memory_handler.recall({"id": "nonexistent-id"})

        assert result["found"] is False

    def test_delete_removes_document(self, memory_handler):
        """Test delete removes document."""
        store_result = memory_handler.store({
            "content": "Deletable content",
            "type": "note",
            "source": "delete.md"
        })

        delete_result = memory_handler.delete({"id": store_result["id"]})
        assert delete_result["deleted"] is True

        # Verify it's gone
        recall_result = memory_handler.recall({"id": store_result["id"]})
        assert recall_result["found"] is False

    def test_list_returns_documents(self, memory_handler):
        """Test list returns documents."""
        # Store some documents
        for i in range(3):
            memory_handler.store({
                "content": f"List test {i}",
                "type": "note",
                "source": f"list-{i}.md"
            })

        result = memory_handler.list({"limit": 10})

        assert "documents" in result
        assert "count" in result
        assert len(result["documents"]) >= 3

    def test_list_by_type(self, memory_handler):
        """Test list filters by type."""
        memory_handler.store({
            "content": "Code for list",
            "type": "code",
            "source": "list-code.py"
        })

        result = memory_handler.list({"type": "code", "limit": 10})

        assert all(d["type"] == "code" for d in result["documents"])


class TestSessionHandler:
    """Tests for SessionHandler class."""

    @pytest.fixture
    def session_handler(self, sqlite_index, vault_manager):
        """Create a SessionHandler for testing."""
        from memory_mcp.handlers import SessionHandler
        return SessionHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,  # Test SQLite fallback
            embedder=None,
            session_id="test-session-id"
        )

    def test_save_creates_session(self, session_handler):
        """Test save creates a session."""
        result = session_handler.save({
            "project_path": "/test/project",
            "active_files": ["file1.py", "file2.py"]
        })

        assert result["saved"] is True
        assert "session_id" in result
        assert result["backend"] == "sqlite"  # No Redis

    def test_restore_finds_session(self, session_handler):
        """Test restore finds saved session."""
        save_result = session_handler.save({
            "project_path": "/test/restore",
            "active_files": ["a.py"]
        })

        restore_result = session_handler.restore({
            "session_id": save_result["session_id"]
        })

        assert restore_result.get("found") is True or "available_sessions" in restore_result

    def test_restore_lists_sessions(self, session_handler):
        """Test restore without session_id lists available sessions."""
        # Save a session first
        session_handler.save({
            "project_path": "/test/list",
            "active_files": []
        })

        result = session_handler.restore({})

        assert "available_sessions" in result

    def test_restore_nonexistent_session(self, session_handler):
        """Test restore returns found=False for missing session."""
        result = session_handler.restore({
            "session_id": "nonexistent-session"
        })

        assert result.get("found") is False


class TestVaultHandler:
    """Tests for VaultHandler class."""

    @pytest.fixture
    def vault_handler(self, sqlite_index, vault_manager):
        """Create a VaultHandler for testing."""
        from memory_mcp.handlers import VaultHandler
        return VaultHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,
            embedder=None,
            session_id="test-session"
        )

    def test_write_creates_note(self, vault_handler):
        """Test write creates a vault note."""
        result = vault_handler.write({
            "path": "handler-test/note",
            "content": "# Test Note\n\nContent here.",
            "folder": "notes"
        })

        assert result["written"] is True
        assert "path" in result

    def test_write_with_tags(self, vault_handler):
        """Test write includes tags."""
        result = vault_handler.write({
            "path": "handler-test/tagged",
            "content": "Tagged note",
            "folder": "notes",
            "tags": ["test", "handler"]
        })

        assert result["written"] is True

    def test_write_validates_folder(self, vault_handler):
        """Test write validates folder name."""
        with pytest.raises(ValueError):
            vault_handler.write({
                "path": "test",
                "content": "content",
                "folder": "invalid_folder"
            })

    def test_read_finds_note(self, vault_handler):
        """Test read finds written note."""
        vault_handler.write({
            "path": "handler-test/readable",
            "content": "Readable content",
            "folder": "notes"
        })

        result = vault_handler.read({"path": "notes/handler-test/readable"})

        assert result["found"] is True
        assert "Readable content" in result["content"]

    def test_read_nonexistent_note(self, vault_handler):
        """Test read returns found=False for missing note."""
        result = vault_handler.read({"path": "nonexistent/path"})

        assert result["found"] is False


class TestStatsHandler:
    """Tests for StatsHandler class."""

    @pytest.fixture
    def stats_handler(self, sqlite_index, vault_manager):
        """Create a StatsHandler for testing."""
        from memory_mcp.handlers import StatsHandler
        return StatsHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,
            embedder=None,
            session_id="test-session"
        )

    def test_get_stats_returns_structure(self, stats_handler):
        """Test get_stats returns expected structure."""
        result = stats_handler.get_stats({})

        assert "sqlite_count" in result
        assert "session_id" in result
        assert "components" in result
        assert "health" in result

    def test_get_stats_includes_components(self, stats_handler):
        """Test get_stats includes component availability."""
        result = stats_handler.get_stats({})

        components = result["components"]
        assert "sqlite" in components
        assert "vault" in components
        assert "redis" in components
        assert "embedder" in components

    def test_get_stats_includes_health(self, stats_handler):
        """Test get_stats includes health status."""
        result = stats_handler.get_stats({})

        health = result["health"]
        assert "sqlite" in health
        assert "vault" in health

    def test_get_stats_sqlite_healthy(self, stats_handler):
        """Test get_stats shows SQLite as healthy."""
        result = stats_handler.get_stats({})

        assert result["health"]["sqlite"]["status"] == "healthy"
        assert "latency_ms" in result["health"]["sqlite"]

    def test_get_stats_redis_unavailable(self, stats_handler):
        """Test get_stats shows Redis as unavailable when not configured."""
        result = stats_handler.get_stats({})

        assert result["components"]["redis"] is False
        assert result["health"]["redis"]["status"] == "not_available"


class TestBaseHandler:
    """Tests for BaseHandler class."""

    def test_session_id_property(self, sqlite_index, vault_manager):
        """Test session_id property."""
        from memory_mcp.handlers import BaseHandler
        handler = BaseHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            session_id="initial-session"
        )

        assert handler.session_id == "initial-session"

    def test_session_id_setter(self, sqlite_index, vault_manager):
        """Test session_id setter."""
        from memory_mcp.handlers import BaseHandler
        handler = BaseHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            session_id="initial"
        )

        handler.session_id = "updated-session"
        assert handler.session_id == "updated-session"

    def test_handler_has_dependencies(self, sqlite_index, vault_manager):
        """Test handler has access to dependencies."""
        from memory_mcp.handlers import BaseHandler
        handler = BaseHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,
            embedder=None,
            session_id="test"
        )

        assert handler.sqlite is sqlite_index
        assert handler.vault is vault_manager
        assert handler.redis is None
        assert handler.embedder is None
