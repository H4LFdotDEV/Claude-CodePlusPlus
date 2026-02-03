# test_redis_client_security.py
# Integration tests for secure deserialization in RedisClient
# Tests the complete flow from Redis to validated SessionState

import pytest
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

# Check if Redis is available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
class TestRedisClientSecureDeserialization:
    """Integration tests for secure deserialization in RedisClient."""

    @pytest.fixture
    def redis_client(self, test_config, mock_redis):
        """Create a Redis client with mocked connection."""
        with patch("memory_mcp.redis_client.redis") as mock_redis_module:
            mock_redis_module.Redis.return_value = mock_redis
            from memory_mcp.redis_client import RedisClient

            client = RedisClient(config=test_config.redis)
            client._client = mock_redis
            client._connected = True
            return client

    # ========================================================================
    # Session Deserialization Tests
    # ========================================================================

    def test_get_session_valid_data(self, redis_client, sample_session_state, mock_redis):
        """Test get_session with valid data."""
        # Set return value for uncompressed key (compressed key returns None)
        mock_redis.get.set_uncompressed_return_value(json.dumps(sample_session_state.to_dict()))

        result = redis_client.get_session(sample_session_state.session_id)

        assert result is not None
        assert result.session_id == sample_session_state.session_id
        assert result.project_path == sample_session_state.project_path
        assert result.active_files == sample_session_state.active_files

    def test_get_session_invalid_session_id_format(self, redis_client, mock_redis):
        """Test get_session rejects invalid session_id format in data."""
        now = datetime.now(timezone.utc).isoformat()
        invalid_data = {
            "session_id": "invalid\r\nFLUSH",  # Redis injection
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(invalid_data))

        result = redis_client.get_session("test")

        assert result is None  # Validation failed

    def test_get_session_malformed_json(self, redis_client, mock_redis, caplog):
        """Test get_session handles malformed JSON gracefully."""
        mock_redis.get.set_uncompressed_return_value("{ invalid json")

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test-session")

        assert result is None
        assert "Failed to parse session JSON" in caplog.text

    def test_get_session_missing_required_field(self, redis_client, mock_redis, caplog):
        """Test get_session rejects data missing required fields."""
        incomplete_data = {
            "session_id": "test",
            "project_path": "path",
            # Missing created_at, updated_at, etc.
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(incomplete_data))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Session data validation failed" in caplog.text

    def test_get_session_invalid_timestamp(self, redis_client, mock_redis, caplog):
        """Test get_session rejects invalid timestamp format."""
        now = datetime.now(timezone.utc).isoformat()
        invalid_data = {
            "session_id": "test",
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": "invalid-timestamp",  # Invalid format
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(invalid_data))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Session data validation failed" in caplog.text

    def test_get_session_path_traversal_attempt(self, redis_client, mock_redis, caplog):
        """Test get_session rejects path traversal in project_path."""
        now = datetime.now(timezone.utc).isoformat()
        traversal_data = {
            "session_id": "test",
            "project_path": "path/to/project/../../../../../../etc/passwd",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(traversal_data))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Session data validation failed" in caplog.text

    def test_get_session_path_traversal_in_files(self, redis_client, mock_redis, caplog):
        """Test get_session rejects path traversal in active_files."""
        now = datetime.now(timezone.utc).isoformat()
        traversal_data = {
            "session_id": "test",
            "project_path": "path",
            "active_files": ["../../../etc/passwd"],  # Traversal attempt
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(traversal_data))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Session data validation failed" in caplog.text

    def test_get_session_extra_fields_rejected(self, redis_client, mock_redis, caplog):
        """Test get_session rejects data with extra unknown fields."""
        now = datetime.now(timezone.utc).isoformat()
        data_with_extras = {
            "session_id": "test",
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
            "malicious_field": "should not be here",  # Extra field
            "another_injection": {"nested": "data"},
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(data_with_extras))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Session data validation failed" in caplog.text

    # ========================================================================
    # Template Deserialization Tests
    # ========================================================================

    def test_get_template_valid_data(self, redis_client, mock_redis):
        """Test get_template with valid data."""
        template_data = {
            "content": "Template content here",
            "metadata": {"version": 1},
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_redis.get.return_value = json.dumps(template_data)

        result = redis_client.get_template("test-template")

        assert result == "Template content here"

    def test_get_template_missing_content_field(self, redis_client, mock_redis, caplog):
        """Test get_template handles missing content field."""
        template_data = {
            "metadata": {"version": 1},
            "cached_at": datetime.now(timezone.utc).isoformat(),
            # Missing 'content' field
        }
        mock_redis.get.return_value = json.dumps(template_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_template("test")

        assert result is None
        assert "Template data validation failed" in caplog.text

    def test_get_template_oversized_metadata(self, redis_client, mock_redis, caplog):
        """Test get_template rejects oversized metadata."""
        template_data = {
            "content": "valid",
            "metadata": {"huge": "x" * 100001},  # Exceeds size limit
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_redis.get.return_value = json.dumps(template_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_template("test")

        assert result is None
        assert "Template data validation failed" in caplog.text

    # ========================================================================
    # Query Cache Deserialization Tests
    # ========================================================================

    def test_get_cached_query_valid_data(self, redis_client, mock_redis):
        """Test get_cached_query with valid data."""
        now = datetime.now(timezone.utc).isoformat()
        query_data = {
            "query": "SELECT * FROM users",
            "result": '{"users": [{"id": 1, "name": "test"}]}',  # Must be string
            "created_at": now,  # Required field (not cached_at)
            "hits": 5,
        }
        mock_redis.get.return_value = json.dumps(query_data)
        mock_redis.setex.return_value = True

        result = redis_client.get_cached_query("SELECT * FROM users")

        assert result == '{"users": [{"id": 1, "name": "test"}]}'
        # Verify hit counter was incremented and saved
        mock_redis.setex.assert_called_once()

    def test_get_cached_query_invalid_embedding_dimension(
        self, redis_client, mock_redis, caplog
    ):
        """Test get_cached_query rejects invalid embedding dimensions."""
        query_data = {
            "query": "test",
            "result": {"answer": "yes"},
            "embedding": [0.1] * 100,  # Too small (< 256)
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "hits": 0,
        }
        mock_redis.get.return_value = json.dumps(query_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_query("test")

        assert result is None
        assert "Query cache validation failed" in caplog.text

    def test_get_cached_query_non_numeric_embedding(
        self, redis_client, mock_redis, caplog
    ):
        """Test get_cached_query rejects non-numeric embedding values."""
        query_data = {
            "query": "test",
            "result": {"answer": "yes"},
            "embedding": ["string"] * 768,  # Non-numeric values
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "hits": 0,
        }
        mock_redis.get.return_value = json.dumps(query_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_query("test")

        assert result is None
        assert "Query cache validation failed" in caplog.text

    def test_get_cached_query_negative_hits(self, redis_client, mock_redis, caplog):
        """Test get_cached_query rejects negative hit counter."""
        query_data = {
            "query": "test",
            "result": {"answer": "yes"},
            "embedding": None,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "hits": -1,  # Invalid
        }
        mock_redis.get.return_value = json.dumps(query_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_query("test")

        assert result is None
        assert "Query cache validation failed" in caplog.text

    # ========================================================================
    # Embedding Cache Deserialization Tests
    # ========================================================================

    def test_get_cached_embedding_valid_data(self, redis_client, mock_redis):
        """Test get_cached_embedding with valid data."""
        now = datetime.now(timezone.utc).isoformat()
        embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        embedding_data = {
            "query": "test text",
            "embedding": embedding,
            "model": "test-model",
            "created_at": now
        }
        mock_redis.get.return_value = json.dumps(embedding_data)

        result = redis_client.get_cached_embedding("test text")

        assert result == embedding
        assert len(result) == 768

    def test_get_cached_embedding_too_small(self, redis_client, mock_redis, caplog):
        """Test get_cached_embedding rejects too small embeddings."""
        now = datetime.now(timezone.utc).isoformat()
        embedding_data = {
            "query": "test",
            "embedding": [0.1] * 100,  # < 256
            "model": "test-model",
            "created_at": now
        }
        mock_redis.get.return_value = json.dumps(embedding_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_embedding("test")

        assert result is None
        assert "Embedding validation failed" in caplog.text

    def test_get_cached_embedding_too_large(self, redis_client, mock_redis, caplog):
        """Test get_cached_embedding rejects too large embeddings."""
        now = datetime.now(timezone.utc).isoformat()
        embedding_data = {
            "query": "test",
            "embedding": [0.1] * 5000,  # > 4096
            "model": "test-model",
            "created_at": now
        }
        mock_redis.get.return_value = json.dumps(embedding_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_embedding("test")

        assert result is None
        assert "Embedding validation failed" in caplog.text

    def test_get_cached_embedding_non_numeric(self, redis_client, mock_redis, caplog):
        """Test get_cached_embedding rejects non-numeric values."""
        now = datetime.now(timezone.utc).isoformat()
        embedding_data = {
            "query": "test",
            "embedding": ["string"] * 768,
            "model": "test-model",
            "created_at": now
        }
        mock_redis.get.return_value = json.dumps(embedding_data)

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_cached_embedding("test")

        assert result is None
        assert "Embedding validation failed" in caplog.text

    # ========================================================================
    # Context Window Deserialization Tests
    # ========================================================================

    def test_get_context_valid_messages(self, redis_client, mock_redis):
        """Test get_context with valid messages."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "Hello", "timestamp": now}),
            json.dumps({"role": "assistant", "content": "Hi there", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        result = redis_client.get_context("test-session")

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_get_context_skips_malformed_json(self, redis_client, mock_redis, caplog):
        """Test get_context skips malformed JSON messages."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "Valid", "timestamp": now}),
            "{ invalid json",  # Malformed
            json.dumps({"role": "assistant", "content": "Also valid", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        with caplog.at_level(logging.WARNING):
            result = redis_client.get_context("test-session")

        assert len(result) == 2  # Only valid messages
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert "Failed to parse context message" in caplog.text

    def test_get_context_skips_invalid_role(self, redis_client, mock_redis, caplog):
        """Test get_context skips messages with invalid role."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "Valid", "timestamp": now}),
            json.dumps({"role": "invalid_role", "content": "Bad role", "timestamp": now}),
            json.dumps({"role": "assistant", "content": "Also valid", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        with caplog.at_level(logging.WARNING):
            result = redis_client.get_context("test-session")

        assert len(result) == 2
        assert "Context message validation failed" in caplog.text

    def test_get_context_skips_missing_required_field(
        self, redis_client, mock_redis, caplog
    ):
        """Test get_context skips messages missing required fields."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "Valid", "timestamp": now}),
            json.dumps({"role": "assistant", "timestamp": now}),  # Missing 'content'
            json.dumps({"role": "user", "content": "Also valid", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        with caplog.at_level(logging.WARNING):
            result = redis_client.get_context("test-session")

        assert len(result) == 2
        assert "Context message validation failed" in caplog.text

    def test_get_context_all_valid_roles(self, redis_client, mock_redis):
        """Test get_context accepts all valid roles."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "Hello", "timestamp": now}),
            json.dumps({"role": "assistant", "content": "Hi", "timestamp": now}),
            json.dumps({"role": "system", "content": "System", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        result = redis_client.get_context("test-session")

        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "system"

    def test_get_context_empty_content_allowed(self, redis_client, mock_redis):
        """Test get_context allows empty message content."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({"role": "user", "content": "", "timestamp": now}),
            json.dumps({"role": "assistant", "content": "Response", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        result = redis_client.get_context("test-session")

        assert len(result) == 2
        assert result[0]["content"] == ""

    def test_get_context_extra_fields_rejected(self, redis_client, mock_redis):
        """Test get_context rejects messages with extra fields (schema has extra=forbid)."""
        now = datetime.now(timezone.utc).isoformat()
        messages = [
            json.dumps({
                "role": "user",
                "content": "Hello",
                "timestamp": now,
                "extra_field": "should cause rejection",
            }),
            json.dumps({"role": "assistant", "content": "Hi", "timestamp": now}),
        ]
        mock_redis.lrange.return_value = messages

        result = redis_client.get_context("test-session")

        assert len(result) == 1  # Only second message is valid (first has extra field)

    # ========================================================================
    # Injection Attack Prevention Tests
    # ========================================================================

    def test_session_id_redis_flush_injection(self, redis_client, mock_redis, caplog):
        """Test prevention of Redis FLUSH command injection."""
        now = datetime.now(timezone.utc).isoformat()
        redis_injection = {
            "session_id": "test\r\nFLUSH ALL\r\n",  # Redis protocol injection
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(redis_injection))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("whatever")

        assert result is None
        assert "Session data validation failed" in caplog.text

    def test_session_id_shell_injection(self, redis_client, mock_redis, caplog):
        """Test prevention of shell command injection."""
        now = datetime.now(timezone.utc).isoformat()
        shell_injection = {
            "session_id": "test; rm -rf /",  # Shell command injection
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(shell_injection))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("whatever")

        assert result is None

    def test_session_id_backtick_injection(self, redis_client, mock_redis, caplog):
        """Test prevention of backtick command substitution."""
        now = datetime.now(timezone.utc).isoformat()
        backtick_injection = {
            "session_id": "test`whoami`",  # Backtick command substitution
            "project_path": "path",
            "active_files": [],
            "recent_queries": [],
            "context_window": [],
            "created_at": now,
            "updated_at": now,
        }
        mock_redis.get.set_uncompressed_return_value(json.dumps(backtick_injection))

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("whatever")

        assert result is None

    def test_redis_error_logging(self, redis_client, mock_redis, caplog):
        """Test Redis errors are logged properly."""
        mock_redis.get.side_effect = redis.RedisError("Connection failed")

        with caplog.at_level(logging.ERROR):
            result = redis_client.get_session("test")

        assert result is None
        assert "Redis error retrieving session" in caplog.text

    # ========================================================================
    # Type Safety Tests
    # ========================================================================

    def test_session_state_maintains_type_safety(self, redis_client, sample_session_state, mock_redis):
        """Test SessionState object has correct types after deserialization."""
        mock_redis.get.set_uncompressed_return_value(json.dumps(sample_session_state.to_dict()))

        session = redis_client.get_session(sample_session_state.session_id)

        assert isinstance(session.session_id, str)
        assert isinstance(session.project_path, str)
        assert isinstance(session.active_files, list)
        assert isinstance(session.recent_queries, list)
        assert isinstance(session.context_window, list)
        assert isinstance(session.created_at, str)
        assert isinstance(session.updated_at, str)

        # Check nested types
        if session.context_window:
            assert isinstance(session.context_window[0], dict)
            assert "role" in session.context_window[0]
            assert "content" in session.context_window[0]

    def test_embedding_type_safety(self, redis_client, mock_redis):
        """Test embedding maintains type safety."""
        now = datetime.now(timezone.utc).isoformat()
        embedding = [0.1, 0.2, 0.3] * 256
        embedding_data = {
            "query": "test",
            "embedding": embedding,
            "model": "test-model",
            "created_at": now
        }
        mock_redis.get.return_value = json.dumps(embedding_data)

        result = redis_client.get_cached_embedding("test")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
        assert len(result) == 768
