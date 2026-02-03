# test_rate_limiter.py
# Tests for rate limiter implementation

import threading
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


class TestRateLimiterThreadSafety:
    """Tests for thread safety of rate limiter."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter with test-friendly settings."""
        from memory_mcp.rate_limiter import RateLimiter
        return RateLimiter(max_requests=100, window_seconds=10)

    def test_concurrent_check_same_client(self, rate_limiter):
        """Test concurrent check() calls for the same client are thread-safe."""
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    result = rate_limiter.check("client1")
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads, each making 10 requests
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have exactly 100 results (10 threads * 10 requests)
        assert len(results) == 100

        # All should be allowed (under the 100 request limit)
        allowed_count = sum(1 for r in results if r.allowed)
        assert allowed_count == 100

        # Final count should be exactly 100
        status = rate_limiter.get_client_status("client1")
        assert status.current_count == 100

    def test_concurrent_check_different_clients(self, rate_limiter):
        """Test concurrent check() calls for different clients."""
        results = []
        errors = []

        def worker(client_id):
            try:
                for _ in range(10):
                    result = rate_limiter.check(client_id)
                    results.append((client_id, result))
            except Exception as e:
                errors.append(e)

        # Launch 5 threads for different clients
        threads = [
            threading.Thread(target=worker, args=(f"client{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have 50 results (5 clients * 10 requests)
        assert len(results) == 50

        # Each client should have exactly 10 requests
        for i in range(5):
            client_id = f"client{i}"
            status = rate_limiter.get_client_status(client_id)
            assert status.current_count == 10

    def test_concurrent_reset_and_check(self, rate_limiter):
        """Test concurrent reset() and check() calls don't cause errors."""
        stop_event = threading.Event()
        errors = []

        def checker():
            try:
                while not stop_event.is_set():
                    rate_limiter.check("client1")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def resetter():
            try:
                while not stop_event.is_set():
                    rate_limiter.reset("client1")
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        # Run checker and resetter concurrently for 0.5 seconds
        checker_thread = threading.Thread(target=checker)
        resetter_thread = threading.Thread(target=resetter)

        checker_thread.start()
        resetter_thread.start()

        time.sleep(0.5)
        stop_event.set()

        checker_thread.join()
        resetter_thread.join()

        # Should complete without errors
        assert len(errors) == 0

    def test_concurrent_stats_and_check(self, rate_limiter):
        """Test concurrent stats() and check() calls don't cause errors."""
        stop_event = threading.Event()
        errors = []
        stats_results = []

        def checker():
            try:
                while not stop_event.is_set():
                    rate_limiter.check("client1")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def stats_reader():
            try:
                while not stop_event.is_set():
                    stats = rate_limiter.stats()
                    stats_results.append(stats)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        # Run checker and stats reader concurrently for 0.5 seconds
        checker_thread = threading.Thread(target=checker)
        stats_thread = threading.Thread(target=stats_reader)

        checker_thread.start()
        stats_thread.start()

        time.sleep(0.5)
        stop_event.set()

        checker_thread.join()
        stats_thread.join()

        # Should complete without errors
        assert len(errors) == 0

        # Stats should have been read successfully
        assert len(stats_results) > 0
        for stats in stats_results:
            assert "active_clients" in stats
            assert "total_requests_in_window" in stats

    def test_concurrent_get_client_status(self, rate_limiter):
        """Test concurrent get_client_status() calls are thread-safe."""
        # Make some requests
        for _ in range(10):
            rate_limiter.check("client1")

        statuses = []
        errors = []

        def worker():
            try:
                for _ in range(20):
                    status = rate_limiter.get_client_status("client1")
                    statuses.append(status)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads reading status concurrently
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have 200 status results
        assert len(statuses) == 200

        # All should report the same count (10)
        for status in statuses:
            assert status.current_count == 10

    def test_no_race_condition_on_limit_boundary(self, rate_limiter):
        """Test that exactly max_requests are allowed with concurrent access."""
        # Create a rate limiter with exactly 50 requests allowed
        strict_limiter = pytest.importorskip("memory_mcp.rate_limiter").RateLimiter(
            max_requests=50, window_seconds=10
        )

        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    result = strict_limiter.check("client1")
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads, each trying to make 10 requests (100 total attempts)
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have exactly 100 results
        assert len(results) == 100

        # Exactly 50 should be allowed
        allowed = [r for r in results if r.allowed]
        denied = [r for r in results if not r.allowed]

        assert len(allowed) == 50
        assert len(denied) == 50

        # Final count should be exactly 50
        status = strict_limiter.get_client_status("client1")
        assert status.current_count == 50


class TestPerToolRateLimiter:
    """Tests for PerToolRateLimiter class."""

    @pytest.fixture
    def per_tool_limiter(self):
        """Create a per-tool rate limiter with test-friendly settings."""
        from memory_mcp.rate_limiter import PerToolRateLimiter
        # Use custom limits for testing
        test_limits = {
            "memory_search": (10, 1),    # 10 per second
            "memory_store": (5, 1),      # 5 per second
            "vault_write": (2, 1),       # 2 per second (I/O intensive)
            "default": (8, 1),           # Default for unlisted tools
        }
        return PerToolRateLimiter(tool_limits=test_limits)

    def test_different_tools_have_independent_limits(self, per_tool_limiter):
        """Test that different tools have independent rate limits."""
        # Use up memory_search limit (10 requests)
        for i in range(10):
            result = per_tool_limiter.check("memory_search", "client1")
            assert result.allowed is True
            assert result.limit == 10

        # memory_search should be blocked
        result = per_tool_limiter.check("memory_search", "client1")
        assert result.allowed is False

        # But vault_write should still be allowed (separate limit)
        result = per_tool_limiter.check("vault_write", "client1")
        assert result.allowed is True
        assert result.limit == 2

    def test_same_tool_different_clients_have_independent_limits(self, per_tool_limiter):
        """Test that the same tool for different clients is tracked separately."""
        # Client 1 uses up memory_search limit
        for _ in range(10):
            per_tool_limiter.check("memory_search", "client1")

        # Client 1 should be blocked
        result = per_tool_limiter.check("memory_search", "client1")
        assert result.allowed is False

        # Client 2 should still be allowed for the same tool
        result = per_tool_limiter.check("memory_search", "client2")
        assert result.allowed is True
        assert result.current_count == 1

    def test_tool_specific_limits_are_enforced(self, per_tool_limiter):
        """Test that each tool enforces its specific limit."""
        # vault_write has limit of 2
        result1 = per_tool_limiter.check("vault_write", "client1")
        result2 = per_tool_limiter.check("vault_write", "client1")
        assert result1.allowed is True
        assert result2.allowed is True

        # 3rd should be blocked
        result3 = per_tool_limiter.check("vault_write", "client1")
        assert result3.allowed is False
        assert result3.limit == 2

    def test_default_limit_for_unlisted_tool(self, per_tool_limiter):
        """Test that unlisted tools use default limit."""
        # "unknown_tool" not in test_limits, should use default (8)
        for i in range(8):
            result = per_tool_limiter.check("unknown_tool", "client1")
            assert result.allowed is True
            assert result.limit == 8

        # 9th should be blocked
        result = per_tool_limiter.check("unknown_tool", "client1")
        assert result.allowed is False

    def test_get_client_status_for_specific_tool(self, per_tool_limiter):
        """Test getting status for specific tool/client combination."""
        # Make some requests
        for _ in range(3):
            per_tool_limiter.check("memory_search", "client1")
        for _ in range(2):
            per_tool_limiter.check("memory_store", "client1")

        # Check status - should not increment
        search_status = per_tool_limiter.get_client_status("memory_search", "client1")
        store_status = per_tool_limiter.get_client_status("memory_store", "client1")

        assert search_status.current_count == 3
        assert search_status.limit == 10
        assert store_status.current_count == 2
        assert store_status.limit == 5

    def test_reset_specific_tool_and_client(self, per_tool_limiter):
        """Test resetting a specific tool/client combination."""
        # Make requests for multiple tools and clients
        per_tool_limiter.check("memory_search", "client1")
        per_tool_limiter.check("memory_search", "client2")
        per_tool_limiter.check("memory_store", "client1")

        # Reset memory_search for client1 only
        per_tool_limiter.reset("memory_search", "client1")

        # memory_search:client1 should be reset
        status = per_tool_limiter.get_client_status("memory_search", "client1")
        assert status.current_count == 0

        # memory_search:client2 should be unaffected
        status = per_tool_limiter.get_client_status("memory_search", "client2")
        assert status.current_count == 1

        # memory_store:client1 should be unaffected
        status = per_tool_limiter.get_client_status("memory_store", "client1")
        assert status.current_count == 1

    def test_reset_all_clients_for_tool(self, per_tool_limiter):
        """Test resetting all clients for a specific tool."""
        # Make requests from multiple clients
        per_tool_limiter.check("memory_search", "client1")
        per_tool_limiter.check("memory_search", "client2")
        per_tool_limiter.check("memory_store", "client1")

        # Reset all clients for memory_search
        per_tool_limiter.reset("memory_search")

        # Both clients for memory_search should be reset
        status1 = per_tool_limiter.get_client_status("memory_search", "client1")
        status2 = per_tool_limiter.get_client_status("memory_search", "client2")
        assert status1.current_count == 0
        assert status2.current_count == 0

        # memory_store should be unaffected
        status = per_tool_limiter.get_client_status("memory_store", "client1")
        assert status.current_count == 1

    def test_reset_all_tools(self, per_tool_limiter):
        """Test resetting all tools and clients."""
        # Make requests for multiple tools and clients
        per_tool_limiter.check("memory_search", "client1")
        per_tool_limiter.check("memory_store", "client1")
        per_tool_limiter.check("vault_write", "client2")

        # Reset everything
        per_tool_limiter.reset()

        # All should be reset
        assert per_tool_limiter.get_client_status("memory_search", "client1").current_count == 0
        assert per_tool_limiter.get_client_status("memory_store", "client1").current_count == 0
        assert per_tool_limiter.get_client_status("vault_write", "client2").current_count == 0

    def test_stats_shows_per_tool_breakdown(self, per_tool_limiter):
        """Test that stats shows per-tool breakdown."""
        # Make requests for different tools
        for _ in range(3):
            per_tool_limiter.check("memory_search", "client1")
        for _ in range(2):
            per_tool_limiter.check("memory_store", "client1")
        per_tool_limiter.check("vault_write", "client2")

        stats = per_tool_limiter.stats()

        # Check structure
        assert "per_tool" in stats
        assert "aggregate" in stats

        # Check per-tool stats
        assert "memory_search" in stats["per_tool"]
        assert "memory_store" in stats["per_tool"]
        assert "vault_write" in stats["per_tool"]

        # Check aggregate stats
        assert stats["aggregate"]["tools_tracked"] == 3
        assert stats["aggregate"]["total_requests_in_window"] == 6

    def test_get_tool_limits(self, per_tool_limiter):
        """Test getting configured tool limits."""
        limits = per_tool_limiter.get_tool_limits()

        assert "memory_search" in limits
        assert "memory_store" in limits
        assert "vault_write" in limits
        assert "default" in limits

        assert limits["memory_search"] == (10, 1)
        assert limits["vault_write"] == (2, 1)
        assert limits["default"] == (8, 1)

    def test_uses_default_tool_limits_when_none_provided(self):
        """Test that default TOOL_LIMITS are used when no custom limits provided."""
        from memory_mcp.rate_limiter import PerToolRateLimiter, TOOL_LIMITS

        limiter = PerToolRateLimiter()
        configured_limits = limiter.get_tool_limits()

        # Should match TOOL_LIMITS
        assert configured_limits == TOOL_LIMITS

    def test_concurrent_access_different_tools(self, per_tool_limiter):
        """Test concurrent access to different tools is thread-safe."""
        results = []
        errors = []

        def worker(tool_name, client_id):
            try:
                for _ in range(5):
                    result = per_tool_limiter.check(tool_name, client_id)
                    results.append((tool_name, client_id, result))
            except Exception as e:
                errors.append(e)

        # Launch threads for different tools
        threads = [
            threading.Thread(target=worker, args=("memory_search", "client1")),
            threading.Thread(target=worker, args=("memory_store", "client1")),
            threading.Thread(target=worker, args=("vault_write", "client1")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 15  # 3 threads * 5 requests

    def test_retry_after_respects_tool_specific_window(self, per_tool_limiter):
        """Test that retry_after is calculated based on tool's window."""
        # Fill up vault_write limit (2 requests, 1 second window)
        per_tool_limiter.check("vault_write", "client1")
        per_tool_limiter.check("vault_write", "client1")

        # Should be blocked with retry_after
        result = per_tool_limiter.check("vault_write", "client1")
        assert result.allowed is False
        assert result.window_seconds == 1
        assert 0 < result.retry_after <= 1.0


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
