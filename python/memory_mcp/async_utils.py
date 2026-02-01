# async_utils.py
# Async/sync bridging utilities for Memory MCP Server
# Jeremiah Kroesche | Halfservers LLC

import asyncio
import logging
from typing import TypeVar, Coroutine, Any

logger = logging.getLogger("memory_mcp")

T = TypeVar("T")

# Default timeout for async operations (seconds)
ASYNC_TIMEOUT_SECONDS = 30.0


def run_async(coro: Coroutine[Any, Any, T], timeout: float = ASYNC_TIMEOUT_SECONDS) -> T:
    """Run an async coroutine from sync context safely.

    Handles the case where we may or may not already be in an async context.
    Includes a timeout to prevent indefinite blocking.

    Args:
        coro: The coroutine to run
        timeout: Maximum time to wait (seconds)

    Returns:
        The result of the coroutine

    Raises:
        asyncio.TimeoutError: If the operation times out
        Exception: Any exception raised by the coroutine
    """
    async def with_timeout():
        return await asyncio.wait_for(coro, timeout=timeout)

    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
        # We're in an async context - use thread-safe execution
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(with_timeout(), loop)
        return future.result(timeout=timeout + 1)  # Extra second for overhead
    except RuntimeError:
        # No running loop - we can use asyncio.run()
        return asyncio.run(with_timeout())


def run_async_no_timeout(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine without timeout (for initialization).

    Use sparingly - prefer run_async() with timeout for most operations.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    except RuntimeError:
        return asyncio.run(coro)
