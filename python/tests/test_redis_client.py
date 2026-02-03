# test_redis_client.py
# Tests for Redis hot cache client

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Check if Redis is available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_session_state_creation(self, sample_session_state):
        """Test creating a session state."""
        assert sample_session_state.session_id == "test-session-001"
        assert len(sample_session_state.active_files) == 2

    def test_session_to_dict(self, sample_session_state):
        """Test converting session to dictionary."""
        d = sample_session_state.to_dict()
        assert isinstance(d, dict)
        assert d["session_id"] == "test-session-001"

    def test_session_from_dict(self, sample_session_state):
        """Test creating session from dictionary."""
        from memory_mcp.redis_client import SessionState
        d = sample_session_state.to_dict()
        restored = SessionState.from_dict(d)
        assert restored.session_id == sample_session_state.session_id


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
class TestRedisClientWithMock:
    """Tests for RedisClient using mocks."""

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

    def test_client_creation(self, redis_client):
        """Test Redis client is created properly."""
        assert redis_client is not None

    def test_connect(self, redis_client, mock_redis):
        """Test connecting to Redis."""
        assert redis_client.is_connected

    def test_save_session(self, redis_client, sample_session_state, mock_redis):
        """Test saving session state."""
        result = redis_client.save_session(sample_session_state)
        assert result is True
        mock_redis.setex.assert_called_once()

    def test_save_session_compressed(self, redis_client, mock_redis):
        """Test saving large session state with compression."""
        from memory_mcp.redis_client import SessionState

        # Create a large session (> 1KB)
        large_session = SessionState(
            session_id="large-session",
            project_path="/test/project",
            active_files=[f"/test/file{i}.py" for i in range(100)],
            recent_queries=["query " * 50 for _ in range(50)],
            context_window=[{"role": "user", "content": "x" * 500} for _ in range(20)],
            created_at="2026-02-02T00:00:00Z",
            updated_at="2026-02-02T00:00:00Z"
        )

        result = redis_client.save_session(large_session)
        assert result is True
        # Verify compressed key format is used (:z suffix)
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].endswith(":z")

    def test_get_session_not_found(self, redis_client, mock_redis):
        """Test getting nonexistent session."""
        mock_redis.get.return_value = None
        result = redis_client.get_session("nonexistent")
        assert result is None

    def test_get_session_found(self, redis_client, sample_session_state, mock_redis):
        """Test getting existing uncompressed session."""
        # Return None for compressed key, JSON for uncompressed
        mock_redis.get.side_effect = lambda key: (
            None if key.endswith(":z") else json.dumps(sample_session_state.to_dict())
        )
        result = redis_client.get_session(sample_session_state.session_id)
        assert result is not None
        assert result.session_id == sample_session_state.session_id

    def test_get_session_compressed(self, redis_client, sample_session_state, mock_redis):
        """Test getting compressed session."""
        import zlib
        import base64

        # Compress session data
        data = json.dumps(sample_session_state.to_dict())
        compressed = zlib.compress(data.encode(), level=6)
        encoded = base64.b64encode(compressed).decode()

        # Mock get to return compressed data for compressed key (:z suffix)
        mock_redis.get.set_compressed_return_value(encoded)
        result = redis_client.get_session(sample_session_state.session_id)
        assert result is not None
        assert result.session_id == sample_session_state.session_id

    def test_delete_session(self, redis_client, mock_redis):
        """Test deleting session (handles both compressed and uncompressed)."""
        mock_redis.delete.return_value = 1
        result = redis_client.delete_session("test-session")
        assert result is True
        # Verify both keys are attempted to be deleted
        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args[0]
        assert len(call_args) == 2  # Both compressed and uncompressed keys

    def test_list_sessions(self, redis_client, mock_redis):
        """Test listing sessions using SCAN (handles both compressed and uncompressed)."""
        # SCAN returns (cursor, keys) - cursor=0 means complete
        # Mix of compressed (:z) and uncompressed sessions
        mock_redis.scan.return_value = (0, [
            "cc:session:sess1",
            "cc:session:sess2:z",
            "cc:session:sess3:z"
        ])
        sessions = redis_client.list_sessions()
        assert len(sessions) == 3
        assert "sess1" in sessions
        assert "sess2" in sessions
        assert "sess3" in sessions

    def test_cache_template(self, redis_client, mock_redis):
        """Test caching a template."""
        result = redis_client.cache_template(
            name="test-template",
            content="Template content here",
            metadata={"version": 1}
        )
        assert result is True

    def test_get_template_not_found(self, redis_client, mock_redis):
        """Test getting nonexistent template."""
        mock_redis.get.return_value = None
        result = redis_client.get_template("nonexistent")
        assert result is None

    def test_get_template_found(self, redis_client, mock_redis):
        """Test getting existing template."""
        mock_redis.get.return_value = json.dumps({
            "content": "Template content",
            "metadata": {},
            "cached_at": datetime.now(timezone.utc).isoformat()
        })
        result = redis_client.get_template("test")
        assert result == "Template content"

    def test_list_templates(self, redis_client, mock_redis):
        """Test listing templates using SCAN."""
        # SCAN returns (cursor, keys) - cursor=0 means complete
        mock_redis.scan.return_value = (0, ["cc:template:t1", "cc:template:t2"])
        templates = redis_client.list_templates()
        assert len(templates) == 2

    def test_cache_query(self, redis_client, mock_redis):
        """Test caching a query result."""
        result = redis_client.cache_query(
            query="test query",
            result={"answer": "test result"},
            embedding=[0.1, 0.2, 0.3]
        )
        assert result is True

    def test_get_cached_query_miss(self, redis_client, mock_redis):
        """Test cache miss for query."""
        mock_redis.get.return_value = None
        result = redis_client.get_cached_query("uncached query")
        assert result is None

    def test_get_cached_query_hit(self, redis_client, mock_redis):
        """Test cache hit for query."""
        now = datetime.now(timezone.utc).isoformat()
        mock_redis.get.return_value = json.dumps({
            "query": "cached query",
            "result": '{"answer": "cached"}',  # Result must be a string
            "created_at": now,
            "hits": 5
        })
        result = redis_client.get_cached_query("cached query")
        assert result == '{"answer": "cached"}'

    def test_cache_embedding(self, redis_client, mock_redis):
        """Test caching an embedding."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = redis_client.cache_embedding(
            text="test text",
            embedding=embedding,
            ttl=3600
        )
        assert result is True

    def test_get_cached_embedding_miss(self, redis_client, mock_redis):
        """Test cache miss for embedding."""
        mock_redis.get.return_value = None
        result = redis_client.get_cached_embedding("uncached text")
        assert result is None

    def test_get_cached_embedding_hit(self, redis_client, mock_redis):
        """Test cache hit for embedding."""
        now = datetime.now(timezone.utc).isoformat()
        # Embedding must be 256-4096 dimensions per validate_embedding_vector
        embedding = [0.1] * 256
        mock_redis.get.return_value = json.dumps({
            "query": "cached text",
            "embedding": embedding,
            "model": "test-model",
            "created_at": now
        })
        result = redis_client.get_cached_embedding("cached text")
        assert result == embedding

    def test_delete_cached_embedding(self, redis_client, mock_redis):
        """Test deleting a cached embedding."""
        mock_redis.delete.return_value = 1
        result = redis_client.delete_cached_embedding("cached text")
        assert result is True
        mock_redis.delete.assert_called_once()

    def test_delete_cached_embedding_not_found(self, redis_client, mock_redis):
        """Test deleting non-existent embedding."""
        mock_redis.delete.return_value = 0
        result = redis_client.delete_cached_embedding("nonexistent")
        assert result is False

    def test_push_context(self, redis_client, mock_redis):
        """Test pushing to context window."""
        message = {"role": "user", "content": "Hello"}
        result = redis_client.push_context("session-id", message)
        assert result is True
        mock_redis.lpush.assert_called_once()

    def test_get_context(self, redis_client, mock_redis):
        """Test getting context window."""
        now = datetime.now(timezone.utc).isoformat()
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "Hi", "timestamp": now}),
            json.dumps({"role": "assistant", "content": "Hello", "timestamp": now})
        ]
        context = redis_client.get_context("session-id", limit=10)
        assert len(context) == 2

    def test_clear_context(self, redis_client, mock_redis):
        """Test clearing context window."""
        mock_redis.delete.return_value = 1
        result = redis_client.clear_context("session-id")
        assert result is True

    def test_get_stats(self, redis_client, mock_redis):
        """Test getting Redis stats."""
        stats = redis_client.get_stats()
        assert "used_memory" in stats
        assert stats["connected"] is True

    def test_health_check(self, redis_client, mock_redis):
        """Test health check."""
        mock_redis.ping.return_value = True
        result = redis_client.health_check()
        assert result is True


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not installed")
class TestRedisClientConnection:
    """Tests for Redis client connection handling."""

    def test_connect_failure(self, test_config):
        """Test handling connection failure."""
        with patch("memory_mcp.redis_client.redis") as mock_redis_module:
            # Need to keep the real exception classes
            mock_redis_module.ConnectionError = redis.ConnectionError
            mock_redis_module.RedisError = redis.RedisError
            mock_instance = MagicMock()
            mock_instance.ping.side_effect = redis.ConnectionError("Connection refused")
            mock_redis_module.Redis.return_value = mock_instance
            from memory_mcp.redis_client import RedisClient

            client = RedisClient(config=test_config.redis)
            result = client.connect()
            assert result is False

    def test_ensure_connected_reconnects(self, test_config, mock_redis):
        """Test that _ensure_connected tries to reconnect."""
        with patch.object(redis, 'Redis', return_value=mock_redis):
            from memory_mcp.redis_client import RedisClient

            client = RedisClient(config=test_config.redis)
            client._connected = False
            client._ensure_connected()
            assert client._connected
