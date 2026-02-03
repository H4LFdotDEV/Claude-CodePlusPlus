# rate_limiter.py
# Rate limiting for MCP server
# Jeremiah Kroesche | Halfservers LLC
#
# Sliding window rate limiter to prevent DoS and resource exhaustion

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# Environment variable configuration
DEFAULT_MAX_REQUESTS = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_MAX", "100"))
DEFAULT_WINDOW_SECONDS = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_WINDOW", "60"))

# Per-tool rate limits: (max_requests, window_seconds)
# Optimized based on resource intensity and typical usage patterns
TOOL_LIMITS: Dict[str, Tuple[int, int]] = {
    "memory_store": (100, 60),      # 100 per minute - moderate writes
    "memory_search": (200, 60),     # 200 per minute - high-frequency reads
    "memory_recall": (200, 60),     # 200 per minute - high-frequency reads
    "memory_list": (100, 60),       # 100 per minute - moderate queries
    "vault_write": (20, 60),        # 20 per minute - I/O intensive
    "vault_read": (50, 60),         # 50 per minute - I/O operations
    "code_search": (50, 60),        # 50 per minute - compute intensive
    "search_function": (50, 60),    # 50 per minute - compute intensive
    "search_class": (50, 60),       # 50 per minute - compute intensive
    "search_entities": (100, 60),   # 100 per minute - graph queries
    "search_facts": (100, 60),      # 100 per minute - graph queries
    "research_capture_store": (30, 60),  # 30 per minute - large files
    "default": (100, 60),           # Default limit for unlisted tools
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    current_count: int
    limit: int
    window_seconds: int
    retry_after: float = 0.0  # Seconds until oldest request expires

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "allowed": self.allowed,
            "current_count": self.current_count,
            "limit": self.limit,
            "window_seconds": self.window_seconds,
            "retry_after": round(self.retry_after, 2)
        }


@dataclass
class RateLimiter:
    """
    Sliding window rate limiter.

    Tracks requests per client ID using a sliding time window.
    Thread-safe for concurrent access using threading.Lock.

    Configuration via environment variables:
    - MEMORY_MCP_RATE_LIMIT_MAX: Maximum requests per window (default: 100)
    - MEMORY_MCP_RATE_LIMIT_WINDOW: Window size in seconds (default: 60)
    """
    max_requests: int = DEFAULT_MAX_REQUESTS
    window_seconds: int = DEFAULT_WINDOW_SECONDS
    _requests: Dict[str, List[float]] = field(default_factory=dict)
    _last_cleanup: float = field(default_factory=time.time)
    _cleanup_interval: float = 300.0  # Clean up stale clients every 5 minutes
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, client_id: str) -> RateLimitResult:
        """
        Check if a request is allowed for the given client.

        Args:
            client_id: Unique identifier for the client/session

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Periodic cleanup of stale client entries
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale_clients(window_start)
                self._last_cleanup = now

            # Initialize client if not present
            if client_id not in self._requests:
                self._requests[client_id] = []

            # Remove expired requests from this client's window
            client_requests = self._requests[client_id]
            valid_requests = [t for t in client_requests if t > window_start]
            self._requests[client_id] = valid_requests

            current_count = len(valid_requests)

            if current_count >= self.max_requests:
                # Calculate retry_after: time until oldest request expires
                oldest = min(valid_requests) if valid_requests else now
                retry_after = max(0.0, oldest + self.window_seconds - now)

                return RateLimitResult(
                    allowed=False,
                    current_count=current_count,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after
                )

            # Record this request
            self._requests[client_id].append(now)

            return RateLimitResult(
                allowed=True,
                current_count=current_count + 1,
                limit=self.max_requests,
                window_seconds=self.window_seconds
            )

    def _cleanup_stale_clients(self, window_start: float) -> None:
        """
        Remove clients with no recent requests to prevent memory growth.

        NOTE: This method must be called while holding self._lock.
        """
        stale_clients = [
            client_id
            for client_id, requests in self._requests.items()
            if not requests or max(requests) <= window_start
        ]
        for client_id in stale_clients:
            del self._requests[client_id]

    def get_client_status(self, client_id: str) -> RateLimitResult:
        """
        Get current rate limit status for a client without recording a request.

        Args:
            client_id: Unique identifier for the client/session

        Returns:
            RateLimitResult with current status
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            if client_id not in self._requests:
                return RateLimitResult(
                    allowed=True,
                    current_count=0,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds
                )

            valid_requests = [t for t in self._requests[client_id] if t > window_start]
            current_count = len(valid_requests)

            if current_count >= self.max_requests:
                oldest = min(valid_requests) if valid_requests else now
                retry_after = max(0.0, oldest + self.window_seconds - now)
                return RateLimitResult(
                    allowed=False,
                    current_count=current_count,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after
                )

            return RateLimitResult(
                allowed=True,
                current_count=current_count,
                limit=self.max_requests,
                window_seconds=self.window_seconds
            )

    def reset(self, client_id: str = None) -> None:
        """
        Reset rate limit state.

        Args:
            client_id: If provided, reset only this client. Otherwise reset all.
        """
        with self._lock:
            if client_id:
                self._requests.pop(client_id, None)
            else:
                self._requests.clear()

    def stats(self) -> Dict:
        """Get rate limiter statistics."""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            active_clients = 0
            total_requests = 0

            for client_id, requests in self._requests.items():
                valid = [t for t in requests if t > window_start]
                if valid:
                    active_clients += 1
                    total_requests += len(valid)

            return {
                "active_clients": active_clients,
                "total_requests_in_window": total_requests,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds
            }


class PerToolRateLimiter:
    """
    Per-tool rate limiter with tool-specific limits.

    Extends the basic rate limiting concept to apply different limits
    per tool type. More resource-intensive tools (vault_write, code_search)
    have lower limits than lightweight operations (memory_search, memory_recall).

    Each tool/client combination is tracked independently using composite keys.
    Falls back to default limits for unlisted tools.

    Example:
        limiter = PerToolRateLimiter()
        result = limiter.check("memory_search", "client_123")
        if not result.allowed:
            print(f"Rate limited. Retry after {result.retry_after}s")

    Integration with MCP server:
        To use per-tool rate limiting in server.py, replace:
            self._rate_limiter = RateLimiter()
            rate_result = self._rate_limiter.check(self._session_id)

        With:
            self._rate_limiter = PerToolRateLimiter()
            # For tools/call method:
            tool_name = params.get("name", "unknown")
            rate_result = self._rate_limiter.check(tool_name, self._session_id)
            # For other methods, use the method name as the tool
    """

    def __init__(self, tool_limits: Dict[str, Tuple[int, int]] = None):
        """
        Initialize per-tool rate limiter.

        Args:
            tool_limits: Optional custom limits dict. Uses TOOL_LIMITS if None.
        """
        self._tool_limits = tool_limits or TOOL_LIMITS
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def _get_limiter(self, tool: str) -> RateLimiter:
        """
        Get or create a RateLimiter for the given tool.

        Args:
            tool: Tool name to get limiter for

        Returns:
            RateLimiter configured with tool-specific limits
        """
        if tool not in self._limiters:
            max_requests, window_seconds = self._tool_limits.get(
                tool,
                self._tool_limits["default"]
            )
            self._limiters[tool] = RateLimiter(
                max_requests=max_requests,
                window_seconds=window_seconds
            )
        return self._limiters[tool]

    def check(self, tool: str, client_id: str) -> RateLimitResult:
        """
        Check if a request is allowed for the given tool and client.

        Uses a composite key of tool:client_id to track limits independently
        per tool. This allows a client to make 200 memory_search requests
        and 20 vault_write requests in the same window.

        Args:
            tool: Tool name being invoked
            client_id: Unique identifier for the client/session

        Returns:
            RateLimitResult with allowed status and tool-specific metadata
        """
        with self._lock:
            limiter = self._get_limiter(tool)

        # Use composite key: tool:client_id for independent tracking
        composite_key = f"{tool}:{client_id}"
        return limiter.check(composite_key)

    def get_client_status(self, tool: str, client_id: str) -> RateLimitResult:
        """
        Get current rate limit status without recording a request.

        Args:
            tool: Tool name to check
            client_id: Unique identifier for the client/session

        Returns:
            RateLimitResult with current status for this tool/client
        """
        with self._lock:
            limiter = self._get_limiter(tool)

        composite_key = f"{tool}:{client_id}"
        return limiter.get_client_status(composite_key)

    def reset(self, tool: str = None, client_id: str = None) -> None:
        """
        Reset rate limit state.

        Args:
            tool: If provided, reset only this tool's limiter
            client_id: If provided with tool, reset only this client for that tool
        """
        with self._lock:
            if tool and tool in self._limiters:
                if client_id:
                    composite_key = f"{tool}:{client_id}"
                    self._limiters[tool].reset(composite_key)
                else:
                    self._limiters[tool].reset()
            elif not tool:
                # Reset all limiters
                for limiter in self._limiters.values():
                    limiter.reset()

    def stats(self) -> Dict:
        """
        Get rate limiter statistics across all tools.

        Returns:
            Dictionary with per-tool statistics and aggregate totals
        """
        with self._lock:
            per_tool_stats = {}
            total_active_clients = 0
            total_requests = 0

            for tool, limiter in self._limiters.items():
                tool_stats = limiter.stats()
                per_tool_stats[tool] = tool_stats
                total_active_clients += tool_stats["active_clients"]
                total_requests += tool_stats["total_requests_in_window"]

            return {
                "per_tool": per_tool_stats,
                "aggregate": {
                    "total_active_clients": total_active_clients,
                    "total_requests_in_window": total_requests,
                    "tools_tracked": len(self._limiters)
                }
            }

    def get_tool_limits(self) -> Dict[str, Tuple[int, int]]:
        """
        Get the configured limits for all tools.

        Returns:
            Dictionary mapping tool names to (max_requests, window_seconds)
        """
        return dict(self._tool_limits)
