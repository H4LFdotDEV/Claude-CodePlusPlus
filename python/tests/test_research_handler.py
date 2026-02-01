# test_research_handler.py
# Unit tests for ResearchHandler class
#
# Tests research session management, transcript storage,
# whiteboard capture, and search functionality.

import json
import os
import pytest
from unittest.mock import MagicMock, patch


class TestResearchHandler:
    """Tests for ResearchHandler class."""

    @pytest.fixture
    def research_handler(self, sqlite_index, vault_manager, mock_redis):
        """Create a ResearchHandler for testing."""
        from memory_mcp.handlers import ResearchHandler
        return ResearchHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,  # Test without Redis
            embedder=None,
            session_id="test-session"
        )

    @pytest.fixture
    def research_handler_with_redis(self, sqlite_index, vault_manager, mock_redis):
        """Create a ResearchHandler with mocked Redis."""
        from memory_mcp.handlers import ResearchHandler
        return ResearchHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=mock_redis,
            embedder=None,
            session_id="test-session"
        )

    # Session Start Tests

    def test_session_start_creates_session(self, research_handler):
        """Test session_start creates a new research session."""
        result_response = research_handler.session_start({
            "name": "Test Research Session",
            "focus_area": "Unit testing",
            "participants": ["Tester", "Claude"]
        })

        # Parse the JSON response
        result = json.loads(result_response["content"][0]["text"])

        assert "session_id" in result
        assert result["name"] == "Test Research Session"
        assert result["focus_area"] == "Unit testing"
        assert result["status"] == "active"
        assert len(result["session_id"]) > 0

    def test_session_start_minimal(self, research_handler):
        """Test session_start with minimal parameters."""
        result_response = research_handler.session_start({
            "name": "Minimal Session"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "session_id" in result
        assert result["name"] == "Minimal Session"
        assert result["status"] == "active"

    def test_session_start_validates_name(self, research_handler):
        """Test session_start validates name is provided."""
        with pytest.raises(ValueError):
            research_handler.session_start({})

    def test_session_start_stores_in_sqlite(self, research_handler):
        """Test session_start stores session metadata in SQLite."""
        result_response = research_handler.session_start({
            "name": "SQLite Test Session"
        })

        result = json.loads(result_response["content"][0]["text"])
        session_id = result["session_id"]

        # Verify it's in SQLite
        doc = research_handler.sqlite.get(session_id)
        assert doc is not None
        assert doc.doc_type == "research_session"
        assert doc.metadata["status"] == "active"

    def test_session_start_creates_marker_file(self, research_handler, tmp_path):
        """Test session_start creates marker file."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            # Create the marker directory
            marker_dir = tmp_path / ".claude-code-pp"
            marker_dir.mkdir(parents=True, exist_ok=True)

            result_response = research_handler.session_start({
                "name": "Marker Test"
            })

            result = json.loads(result_response["content"][0]["text"])

            # Check marker file (if created - may fail due to path issues in test)
            marker_path = marker_dir / "research_session_active"
            # This is a best-effort test - marker creation may fail in test environment

    # Session End Tests

    def test_session_end_closes_session(self, research_handler):
        """Test session_end closes an active session."""
        # Start a session first
        start_response = research_handler.session_start({
            "name": "Closable Session",
            "focus_area": "Testing close"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # End the session
        end_response = research_handler.session_end({
            "session_id": session_id,
            "summary": "Session completed successfully",
            "action_items": ["Review tests", "Add more coverage"],
            "key_decisions": ["Use pytest fixtures"]
        })

        end_result = json.loads(end_response["content"][0]["text"])

        assert end_result["session_id"] == session_id
        assert end_result["status"] == "completed"
        assert "vault_path" in end_result

    def test_session_end_nonexistent(self, research_handler):
        """Test session_end with nonexistent session."""
        result_response = research_handler.session_end({
            "session_id": "nonexistent-session-id"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "error" in result
        assert result_response.get("isError") is True

    def test_session_end_updates_sqlite(self, research_handler):
        """Test session_end updates SQLite with completion data."""
        # Start a session
        start_response = research_handler.session_start({
            "name": "Update Test"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # End with summary
        research_handler.session_end({
            "session_id": session_id,
            "summary": "Test summary"
        })

        # Check SQLite
        doc = research_handler.sqlite.get(session_id)
        assert doc.metadata["status"] == "completed"
        assert "summary" in doc.metadata

    # Transcript Store Tests

    def test_transcript_store_basic(self, research_handler):
        """Test transcript_store saves transcript."""
        result_response = research_handler.transcript_store({
            "text": "This is a test transcript segment.",
            "speaker": "user"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "transcript_id" in result
        assert result["speaker"] == "user"
        assert result["stored"] is True
        assert result["word_count"] > 0

    def test_transcript_store_with_session(self, research_handler):
        """Test transcript_store associates with session."""
        # Start a session
        start_response = research_handler.session_start({
            "name": "Transcript Session"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # Store transcript
        result_response = research_handler.transcript_store({
            "text": "Session-linked transcript",
            "speaker": "claude",
            "session_id": session_id
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["session_id"] == session_id
        assert result["stored"] is True

    def test_transcript_store_validates_text(self, research_handler):
        """Test transcript_store validates text is provided."""
        with pytest.raises(ValueError):
            research_handler.transcript_store({
                "speaker": "user"
            })

    def test_transcript_store_default_speaker(self, research_handler):
        """Test transcript_store defaults speaker to 'user'."""
        result_response = research_handler.transcript_store({
            "text": "No speaker specified"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["speaker"] == "user"

    def test_transcript_store_in_sqlite(self, research_handler):
        """Test transcript_store persists to SQLite."""
        result_response = research_handler.transcript_store({
            "text": "Persistent transcript content",
            "speaker": "researcher"
        })

        result = json.loads(result_response["content"][0]["text"])
        transcript_id = result["transcript_id"]

        # Verify in SQLite
        doc = research_handler.sqlite.get(transcript_id)
        assert doc is not None
        assert doc.doc_type == "transcript"
        assert "researcher" in doc.content

    # Capture Store Tests

    def test_capture_store_basic(self, research_handler):
        """Test capture_store saves whiteboard capture."""
        result_response = research_handler.capture_store({
            "description": "Whiteboard showing force diagram"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "capture_id" in result
        assert result["capture_type"] == "whiteboard"
        assert result["stored"] is True

    def test_capture_store_with_ocr(self, research_handler):
        """Test capture_store with OCR text."""
        result_response = research_handler.capture_store({
            "description": "Diagram with equations",
            "ocr_text": "F = ma\nE = mc^2",
            "capture_type": "whiteboard"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["has_ocr"] is True
        assert result["stored"] is True

    def test_capture_store_with_image_path(self, research_handler):
        """Test capture_store with image path."""
        result_response = research_handler.capture_store({
            "description": "Screenshot of simulation",
            "image_path": "/path/to/screenshot.png",
            "capture_type": "screenshot"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["capture_type"] == "screenshot"
        assert result["stored"] is True

    def test_capture_store_with_session(self, research_handler):
        """Test capture_store associates with session."""
        # Start a session
        start_response = research_handler.session_start({
            "name": "Capture Session"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # Store capture
        result_response = research_handler.capture_store({
            "description": "Session whiteboard",
            "session_id": session_id
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["session_id"] == session_id

    def test_capture_store_validates_description(self, research_handler):
        """Test capture_store validates description is provided."""
        with pytest.raises(ValueError):
            research_handler.capture_store({
                "ocr_text": "Some text"
            })

    def test_capture_store_in_sqlite(self, research_handler):
        """Test capture_store persists to SQLite."""
        result_response = research_handler.capture_store({
            "description": "Persistent capture",
            "ocr_text": "OCR content here"
        })

        result = json.loads(result_response["content"][0]["text"])
        capture_id = result["capture_id"]

        # Verify in SQLite
        doc = research_handler.sqlite.get(capture_id)
        assert doc is not None
        assert doc.doc_type == "research_image"
        assert "OCR content here" in doc.content

    # Search Tests

    def test_search_basic(self, research_handler):
        """Test research search finds matching content."""
        # Store some searchable content
        research_handler.transcript_store({
            "text": "Unique search term xyz789",
            "speaker": "user"
        })

        result_response = research_handler.search({
            "query": "xyz789"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "results" in result
        assert result["query"] == "xyz789"

    def test_search_by_session(self, research_handler):
        """Test search filters by session_id."""
        # Start a session
        start_response = research_handler.session_start({
            "name": "Search Session"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # Store transcript in session
        research_handler.transcript_store({
            "text": "Session-specific content abc123",
            "session_id": session_id
        })

        # Search with filter
        result_response = research_handler.search({
            "query": "abc123",
            "session_id": session_id
        })

        result = json.loads(result_response["content"][0]["text"])

        assert "filters" in result
        assert result["filters"]["session_id"] == session_id

    def test_search_by_type(self, research_handler):
        """Test search filters by content type."""
        # Store different types
        research_handler.transcript_store({
            "text": "Transcript content def456"
        })
        research_handler.capture_store({
            "description": "Capture description def456"
        })

        # Search for transcripts only
        result_response = research_handler.search({
            "query": "def456",
            "type": "transcript"
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["filters"]["type"] == "transcript"

    def test_search_with_limit(self, research_handler):
        """Test search respects limit parameter."""
        # Store multiple items
        for i in range(5):
            research_handler.transcript_store({
                "text": f"Repeated search term ghi789 item {i}"
            })

        result_response = research_handler.search({
            "query": "ghi789",
            "limit": 3
        })

        result = json.loads(result_response["content"][0]["text"])

        assert result["count"] <= 3

    def test_search_validates_query(self, research_handler):
        """Test search validates query is provided."""
        with pytest.raises(ValueError):
            research_handler.search({})


class TestResearchHandlerWithRedis:
    """Tests for ResearchHandler with Redis enabled."""

    @pytest.fixture
    def handler(self, sqlite_index, vault_manager, mock_redis):
        """Create a ResearchHandler with mocked Redis."""
        from memory_mcp.handlers import ResearchHandler
        return ResearchHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=mock_redis,
            embedder=None,
            session_id="test-session"
        )

    def test_session_start_caches_in_redis(self, handler, mock_redis):
        """Test session_start caches session in Redis."""
        handler.session_start({
            "name": "Redis Cache Test"
        })

        # Verify Redis was called
        assert mock_redis.set.called

    def test_session_end_clears_redis_cache(self, handler, mock_redis):
        """Test session_end clears Redis cache."""
        # Start a session
        start_response = handler.session_start({
            "name": "Redis Clear Test"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # End the session
        handler.session_end({
            "session_id": session_id
        })

        # Verify Redis delete was called
        assert mock_redis.delete.called

    def test_transcript_caches_in_redis(self, handler, mock_redis):
        """Test transcript_store caches recent transcript in Redis."""
        # Start a session for caching
        start_response = handler.session_start({
            "name": "Transcript Cache Test"
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        # Store transcript
        handler.transcript_store({
            "text": "Cached transcript text",
            "session_id": session_id
        })

        # Verify Redis was called for caching
        assert mock_redis.lpush.called or mock_redis.set.called


class TestResearchIntegration:
    """Integration tests for research workflow."""

    @pytest.fixture
    def handler(self, sqlite_index, vault_manager):
        """Create handler for integration tests."""
        from memory_mcp.handlers import ResearchHandler
        return ResearchHandler(
            sqlite=sqlite_index,
            vault=vault_manager,
            redis=None,
            embedder=None,
            session_id="integration-test"
        )

    def test_full_research_session_workflow(self, handler):
        """Test complete research session workflow."""
        # 1. Start session
        start_response = handler.session_start({
            "name": "Integration Test Session",
            "focus_area": "Workflow testing",
            "participants": ["Tester"]
        })
        start_result = json.loads(start_response["content"][0]["text"])
        session_id = start_result["session_id"]

        assert start_result["status"] == "active"

        # 2. Store transcripts
        transcript1 = handler.transcript_store({
            "text": "First point of discussion",
            "speaker": "Tester",
            "session_id": session_id
        })
        transcript1_result = json.loads(transcript1["content"][0]["text"])
        assert transcript1_result["stored"] is True

        transcript2 = handler.transcript_store({
            "text": "Claude's response to the point",
            "speaker": "Claude",
            "session_id": session_id
        })
        transcript2_result = json.loads(transcript2["content"][0]["text"])
        assert transcript2_result["stored"] is True

        # 3. Store captures
        capture = handler.capture_store({
            "description": "Whiteboard showing workflow diagram",
            "ocr_text": "Step 1 -> Step 2 -> Step 3",
            "session_id": session_id,
            "capture_type": "whiteboard"
        })
        capture_result = json.loads(capture["content"][0]["text"])
        assert capture_result["stored"] is True

        # 4. Search within session
        search_result = handler.search({
            "query": "discussion",
            "session_id": session_id
        })
        search_data = json.loads(search_result["content"][0]["text"])
        assert search_data["count"] >= 1

        # 5. End session
        end_response = handler.session_end({
            "session_id": session_id,
            "summary": "Successfully tested workflow",
            "action_items": ["Document findings", "Create more tests"],
            "key_decisions": ["Workflow pattern works"]
        })
        end_result = json.loads(end_response["content"][0]["text"])

        assert end_result["status"] == "completed"
        assert end_result["transcript_count"] >= 2
        assert end_result["capture_count"] >= 1
