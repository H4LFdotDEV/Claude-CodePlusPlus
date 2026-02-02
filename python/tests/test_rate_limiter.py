# test_rate_limiter.py
# Tests for rate limiter implementation

import time
import pytest
from unittest.mock import patch


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter with test-friendly settings."""
        from memory_mcp.rate_limiter import RateLimiter
        return RateLimiter(max_requests=5, window_seconds=1)

    def test_allows_requests_under_limit(self, rate_limiter):
        """Test that requests under the limit are allowed."""
        for i in range(5):
            result = rate_limiter.check("client1")
            assert result.allowed is True
            assert result.current_count == i + 1
            assert result.limit == 5

    def test_blocks_requests_over_limit(self, rate_limiter):
        """Test that requests over the limit are blocked."""
        # Use all 5 requests
        for _ in range(5):
            rate_limiter.check("client1")

        # 6th request should be blocked
        result = rate_limiter.check("client1")
        assert result.allowed is False
        assert result.current_count == 5
        assert result.retry_after > 0

    def test_sliding_window_expires_old_requests(self, rate_limiter):
        """Test that old requests expire and new ones are allowed."""
        # Use all 5 requests
        for _ in range(5):
            rate_limiter.check("client1")

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        result = rate_limiter.check("client1")
        assert result.allowed is True
        assert result.current_count == 1

    def test_independent_client_limits(self, rate_limiter):
        """Test that different clients have independent limits."""
        # Client 1 uses all requests
        for _ in range(5):
            rate_limiter.check("client1")

        # Client 2 should still be allowed
        result = rate_limiter.check("client2")
        assert result.allowed is True
        assert result.current_count == 1

        # Client 1 should still be blocked
        result = rate_limiter.check("client1")
        assert result.allowed is False

    def test_get_client_status_without_recording(self, rate_limiter):
        """Test getting status without recording a request."""
        # Make 3 requests
        for _ in range(3):
            rate_limiter.check("client1")

        # Get status - should not increment
        status = rate_limiter.get_client_status("client1")
        assert status.current_count == 3
        assert status.allowed is True

        # Verify count didn't change
        status2 = rate_limiter.get_client_status("client1")
        assert status2.current_count == 3

    def test_get_status_for_unknown_client(self, rate_limiter):
        """Test getting status for a client with no requests."""
        status = rate_limiter.get_client_status("unknown_client")
        assert status.current_count == 0
        assert status.allowed is True
        assert status.limit == 5

    def test_reset_single_client(self, rate_limiter):
        """Test resetting a single client's limits."""
        # Use some requests
        for _ in range(3):
            rate_limiter.check("client1")
            rate_limiter.check("client2")

        # Reset client1
        rate_limiter.reset("client1")

        # Client1 should be reset
        status1 = rate_limiter.get_client_status("client1")
        assert status1.current_count == 0

        # Client2 should be unaffected
        status2 = rate_limiter.get_client_status("client2")
        assert status2.current_count == 3

    def test_reset_all_clients(self, rate_limiter):
        """Test resetting all clients."""
        # Use some requests
        for _ in range(3):
            rate_limiter.check("client1")
            rate_limiter.check("client2")

        # Reset all
        rate_limiter.reset()

        # Both should be reset
        status1 = rate_limiter.get_client_status("client1")
        status2 = rate_limiter.get_client_status("client2")
        assert status1.current_count == 0
        assert status2.current_count == 0

    def test_stats(self, rate_limiter):
        """Test statistics gathering."""
        # Make some requests from different clients
        for _ in range(3):
            rate_limiter.check("client1")
        for _ in range(2):
            rate_limiter.check("client2")

        stats = rate_limiter.stats()
        assert stats["active_clients"] == 2
        assert stats["total_requests_in_window"] == 5
        assert stats["max_requests"] == 5
        assert stats["window_seconds"] == 1

    def test_retry_after_calculation(self, rate_limiter):
        """Test retry_after is calculated correctly."""
        # Fill up the limit
        for _ in range(5):
            rate_limiter.check("client1")

        # Check retry_after
        result = rate_limiter.check("client1")
        assert result.allowed is False
        # retry_after should be close to window_seconds (1s)
        assert 0 < result.retry_after <= 1.0

    def test_result_to_dict(self, rate_limiter):
        """Test RateLimitResult.to_dict() method."""
        result = rate_limiter.check("client1")
        result_dict = result.to_dict()

        assert "allowed" in result_dict
        assert "current_count" in result_dict
        assert "limit" in result_dict
        assert "window_seconds" in result_dict
        assert "retry_after" in result_dict
        assert result_dict["allowed"] is True
        assert result_dict["current_count"] == 1


class TestRateLimiterEnvironment:
    """Tests for environment variable configuration."""

    def test_default_values(self):
        """Test default values without environment variables."""
        from memory_mcp.rate_limiter import RateLimiter
        limiter = RateLimiter()
        # Defaults should be 100 requests per 60 seconds
        assert limiter.max_requests == 100
        assert limiter.window_seconds == 60

    def test_environment_variables(self):
        """Test configuration via environment variables."""
        with patch.dict("os.environ", {
            "MEMORY_MCP_RATE_LIMIT_MAX": "50",
            "MEMORY_MCP_RATE_LIMIT_WINDOW": "30"
        }):
            # Need to reimport to pick up new env vars
            import importlib
            import memory_mcp.rate_limiter as rl_module
            importlib.reload(rl_module)

            limiter = rl_module.RateLimiter()
            assert limiter.max_requests == 50
            assert limiter.window_seconds == 30

            # Restore defaults
            with patch.dict("os.environ", {
                "MEMORY_MCP_RATE_LIMIT_MAX": "100",
                "MEMORY_MCP_RATE_LIMIT_WINDOW": "60"
            }):
                importlib.reload(rl_module)


class TestRateLimiterCleanup:
    """Tests for stale client cleanup."""

    def test_cleanup_stale_clients(self):
        """Test that stale clients are cleaned up."""
        from memory_mcp.rate_limiter import RateLimiter

        # Create limiter with short cleanup interval for testing
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        limiter._cleanup_interval = 0.1  # 100ms

        # Make requests from multiple clients
        limiter.check("client1")
        limiter.check("client2")

        # Wait for requests to expire
        time.sleep(1.1)

        # Trigger cleanup via check (which happens after cleanup interval)
        time.sleep(0.15)
        limiter.check("client3")

        # Stale clients should be cleaned up
        # (their lists should be empty or removed)
        stats = limiter.stats()
        assert stats["active_clients"] == 1
        assert stats["total_requests_in_window"] == 1


class TestServerRateLimitIntegration:
    """Tests for rate limiting integration with MCP server."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        server = MemoryMCPServer(config=test_config)
        # Use a strict rate limiter for testing
        from memory_mcp.rate_limiter import RateLimiter
        server._rate_limiter = RateLimiter(max_requests=3, window_seconds=1)
        return server

    def test_rate_limit_in_handle_request(self, mcp_server):
        """Test rate limiting is applied in _handle_request."""
        # First 3 requests should succeed
        for _ in range(3):
            response = mcp_server._handle_request({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            })
            assert "error" not in response

        # 4th request should be rate limited
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        assert "error" in response
        assert response["error"]["code"] == -32000
        assert "Rate limit exceeded" in response["error"]["message"]

    def test_initialize_skips_rate_limit(self, mcp_server):
        """Test that initialize method skips rate limiting."""
        # Use up the rate limit
        for _ in range(3):
            mcp_server._handle_request({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            })

        # Initialize should still work
        response = mcp_server._handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {}
        })
        assert "error" not in response
        assert "result" in response

    def test_memory_stats_includes_rate_limiter(self, mcp_server):
        """Test that memory_stats includes rate limiter info."""
        result = mcp_server.handle_call_tool("memory_stats", {})
        import json
        data = json.loads(result["content"][0]["text"])

        assert "rate_limiter" in data
        assert "health" in data
        assert "rate_limiter" in data["health"]
        assert data["health"]["rate_limiter"]["status"] == "active"

        # Check rate limiter stats structure
        rl_stats = data["rate_limiter"]
        assert "max_requests" in rl_stats
        assert "window_seconds" in rl_stats
        assert "current_session" in rl_stats
