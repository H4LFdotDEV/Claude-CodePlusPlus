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
