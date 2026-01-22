"""
Tests for Enhanced Memory Stats.

Tests the enhanced memory_stats tool output including:
- Component health checks with latency
- Redis health status
- Embedder dimension info
"""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestEnhancedStatsFormat:
    """Test the enhanced stats response format."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_stats_includes_health_section(self, mcp_server):
        """Test that stats response includes health section."""
        result = mcp_server.handle_call_tool("memory_stats", {})

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])

        assert "health" in data
        assert isinstance(data["health"], dict)

    def test_stats_includes_sqlite_health(self, mcp_server):
        """Test SQLite health check in stats."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert "sqlite" in data["health"]
        assert data["health"]["sqlite"]["status"] == "healthy"
        assert "latency_ms" in data["health"]["sqlite"]
        assert isinstance(data["health"]["sqlite"]["latency_ms"], (int, float))

    def test_stats_includes_vault_health(self, mcp_server):
        """Test Vault health check in stats."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert "vault" in data["health"]
        assert data["health"]["vault"]["status"] == "connected"
        assert "latency_ms" in data["health"]["vault"]

    def test_stats_includes_components_boolean(self, mcp_server):
        """Test components section has boolean values."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert "components" in data
        assert isinstance(data["components"]["sqlite"], bool)
        assert isinstance(data["components"]["vault"], bool)
        assert isinstance(data["components"]["redis"], bool)
        assert isinstance(data["components"]["embedder"], bool)

    def test_stats_includes_session_id(self, mcp_server):
        """Test session_id is present in stats."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0


class TestEnhancedStatsWithRedis:
    """Test enhanced stats with Redis available."""

    def test_redis_health_when_available(self, test_config):
        """Test Redis health check when connected."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", True):
            with patch("memory_mcp.server.RedisClient") as MockRedis:
                mock_client = MagicMock()
                mock_client.connect.return_value = True
                mock_client.health_check.return_value = True
                mock_client.get_stats.return_value = {
                    "connected": True,
                    "used_memory": "1.5M",
                    "peak_memory": "2.0M"
                }
                MockRedis.return_value = mock_client

                from memory_mcp.server import MemoryMCPServer
                server = MemoryMCPServer(config=test_config)

                result = server.handle_call_tool("memory_stats", {})
                data = json.loads(result["content"][0]["text"])

                assert data["health"]["redis"]["status"] == "healthy"
                assert "latency_ms" in data["health"]["redis"]
                assert data["redis"]["connected"] is True

    def test_redis_health_when_degraded(self, test_config):
        """Test Redis health check when degraded."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", True):
            with patch("memory_mcp.server.RedisClient") as MockRedis:
                mock_client = MagicMock()
                mock_client.connect.return_value = True
                mock_client.health_check.return_value = False  # Degraded
                mock_client.get_stats.return_value = {"connected": True}
                MockRedis.return_value = mock_client

                from memory_mcp.server import MemoryMCPServer
                server = MemoryMCPServer(config=test_config)

                result = server.handle_call_tool("memory_stats", {})
                data = json.loads(result["content"][0]["text"])

                assert data["health"]["redis"]["status"] == "degraded"


class TestEnhancedStatsWithEmbedder:
    """Test enhanced stats with embedder available."""

    def test_embedder_includes_dimension(self, test_config, mock_embedding_provider):
        """Test embedder stats include dimension when available."""
        with patch("memory_mcp.server.get_embedding_provider") as mock_get_provider:
            mock_provider = mock_embedding_provider
            mock_provider.name = "local/nomic-embed"
            mock_provider.dimension = 768
            mock_get_provider.return_value = mock_provider

            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            result = server.handle_call_tool("memory_stats", {})
            data = json.loads(result["content"][0]["text"])

            assert "embedder" in data
            assert data["embedder"]["provider"] == "local/nomic-embed"
            assert data["health"]["embedder"]["status"] == "active"


class TestEnhancedStatsErrors:
    """Test error handling in enhanced stats."""

    def test_sqlite_error_captured_in_health(self, test_config):
        """Test SQLite errors are captured in health status."""
        from memory_mcp.server import MemoryMCPServer
        server = MemoryMCPServer(config=test_config)

        # Simulate SQLite error
        server.sqlite.get_stats = MagicMock(side_effect=Exception("SQLite error"))

        result = server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert data["health"]["sqlite"]["status"] == "error"
        assert "SQLite error" in data["health"]["sqlite"]["error"]

    def test_vault_error_captured_in_health(self, test_config):
        """Test Vault errors are captured in health status."""
        from memory_mcp.server import MemoryMCPServer
        server = MemoryMCPServer(config=test_config)

        # Simulate Vault error
        server.vault.get_stats = MagicMock(side_effect=Exception("Vault error"))

        result = server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        assert data["health"]["vault"]["status"] == "error"
        assert "Vault error" in data["health"]["vault"]["error"]


class TestEnhancedStatsUnavailable:
    """Test stats when components are unavailable."""

    def test_redis_not_available_status(self, test_config):
        """Test Redis health shows not_available when not configured."""
        with patch("memory_mcp.server.REDIS_AVAILABLE", False):
            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            result = server.handle_call_tool("memory_stats", {})
            data = json.loads(result["content"][0]["text"])

            assert data["health"]["redis"]["status"] == "not_available"
            assert data["components"]["redis"] is False

    def test_embedder_not_available_status(self, test_config):
        """Test embedder health shows not_available when not configured."""
        with patch("memory_mcp.server.get_embedding_provider") as mock_get_provider:
            mock_get_provider.return_value = None

            from memory_mcp.server import MemoryMCPServer
            server = MemoryMCPServer(config=test_config)

            result = server.handle_call_tool("memory_stats", {})
            data = json.loads(result["content"][0]["text"])

            assert data["health"]["embedder"]["status"] == "not_available"
            assert data["components"]["embedder"] is False


class TestStatsLatency:
    """Test latency measurements in stats."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_latency_is_positive_number(self, mcp_server):
        """Test latency values are positive numbers."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        # SQLite latency should exist and be positive
        assert data["health"]["sqlite"]["latency_ms"] >= 0

        # Vault latency should exist and be positive
        assert data["health"]["vault"]["latency_ms"] >= 0

    def test_latency_is_reasonable(self, mcp_server):
        """Test latency values are within reasonable bounds."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        data = json.loads(result["content"][0]["text"])

        # Local operations should complete in under 1 second
        assert data["health"]["sqlite"]["latency_ms"] < 1000
        assert data["health"]["vault"]["latency_ms"] < 1000
