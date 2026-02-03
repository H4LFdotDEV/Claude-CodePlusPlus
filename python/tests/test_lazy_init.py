"""Tests for lazy initialization in MemoryMCPServer."""

import time
import pytest
from unittest.mock import Mock, patch

from memory_mcp.server import LazyService, MemoryMCPServer


class TestLazyService:
    """Tests for the LazyService wrapper class."""

    def test_lazy_service_not_initialized_on_creation(self):
        """Service should not be initialized until accessed."""
        factory = Mock(return_value="test_value")
        lazy = LazyService(factory, "test")

        assert not lazy.initialized
        assert not lazy.available
        factory.assert_not_called()

    def test_lazy_service_initializes_on_first_access(self):
        """Service should initialize on first get() call."""
        factory = Mock(return_value="test_value")
        lazy = LazyService(factory, "test")

        result = lazy.get()

        assert result == "test_value"
        assert lazy.initialized
        assert lazy.available
        factory.assert_called_once()

    def test_lazy_service_caches_result(self):
        """Service should only initialize once, returning cached value."""
        factory = Mock(return_value="test_value")
        lazy = LazyService(factory, "test")

        result1 = lazy.get()
        result2 = lazy.get()
        result3 = lazy.get()

        assert result1 == result2 == result3 == "test_value"
        factory.assert_called_once()  # Only called once

    def test_lazy_service_handles_factory_exception(self):
        """Service should handle factory exceptions gracefully."""
        factory = Mock(side_effect=Exception("Init failed"))
        lazy = LazyService(factory, "test")

        result = lazy.get()

        assert result is None
        assert not lazy.initialized
        assert lazy._init_attempted
        assert lazy._init_error is not None

    def test_lazy_service_does_not_retry_after_failure(self):
        """Service should not retry initialization after failure."""
        factory = Mock(side_effect=Exception("Init failed"))
        lazy = LazyService(factory, "test")

        result1 = lazy.get()
        result2 = lazy.get()

        assert result1 is None
        assert result2 is None
        factory.assert_called_once()  # Only tried once

    def test_lazy_service_reset(self):
        """Service should be re-initializable after reset."""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return f"value_{call_count}"

        lazy = LazyService(factory, "test")

        result1 = lazy.get()
        lazy.reset()
        result2 = lazy.get()

        assert result1 == "value_1"
        assert result2 == "value_2"
        assert call_count == 2

    def test_lazy_service_thread_safety(self):
        """Service should be thread-safe for concurrent access."""
        import threading

        init_count = 0
        init_lock = threading.Lock()

        def slow_factory():
            nonlocal init_count
            time.sleep(0.1)  # Simulate slow init
            with init_lock:
                init_count += 1
            return "value"

        lazy = LazyService(slow_factory, "test")
        results = []

        def access_service():
            results.append(lazy.get())

        threads = [threading.Thread(target=access_service) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the same
        assert all(r == "value" for r in results)
        # Factory should only be called once despite concurrent access
        assert init_count == 1


class TestMemoryMCPServerLazyInit:
    """Tests for lazy initialization in MemoryMCPServer."""

    def test_server_init_is_fast(self):
        """Server initialization should be fast with lazy loading."""
        start = time.time()
        server = MemoryMCPServer()
        init_time = time.time() - start

        # Should be under 100ms without eager initialization
        assert init_time < 0.1, f"Server init took {init_time*1000:.1f}ms, expected < 100ms"

    def test_server_optional_services_not_initialized_on_startup(self):
        """Optional services should not be initialized on server creation."""
        server = MemoryMCPServer()

        assert not server._lazy_redis.initialized
        assert not server._lazy_graphiti.initialized
        assert not server._lazy_livegrep.initialized
        assert not server._lazy_embedder.initialized

    def test_server_core_services_always_initialized(self):
        """Core services (sqlite, vault) should always be initialized."""
        server = MemoryMCPServer()

        assert server.sqlite is not None
        assert server.vault is not None

    def test_server_eager_init_mode(self):
        """Server with eager_init=True should initialize all services."""
        server = MemoryMCPServer(eager_init=True)

        # Handlers should be initialized
        assert server._handlers_initialized
        assert server._memory_handler is not None

    def test_server_handlers_initialize_on_first_tool_call(self):
        """Handlers should initialize when first tool is called."""
        server = MemoryMCPServer()

        assert not server._handlers_initialized

        # Call a tool
        server.handle_call_tool("memory_list", {"limit": 1})

        assert server._handlers_initialized
        assert server._memory_handler is not None

    def test_server_lazy_redis_property(self):
        """Redis property should trigger lazy initialization."""
        server = MemoryMCPServer()

        assert not server._lazy_redis.initialized

        # Access redis property
        _ = server.redis

        assert server._lazy_redis.initialized
