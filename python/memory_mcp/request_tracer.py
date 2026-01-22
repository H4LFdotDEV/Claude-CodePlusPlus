"""
Request Tracing System for Memory MCP Server.

Provides request tracing capabilities for debugging and performance analysis:
- Assigns unique request_id to every MCP tool invocation
- Logs request/response/error with timestamps
- Tracks request flow through memory tiers (SQLite, Redis, FAISS)
- Performance profiling per request

Usage:
    from memory_mcp.request_tracer import trace_request, get_tracer

    @trace_request
    async def handle_memory_store(arguments: dict) -> dict:
        # Existing logic with automatic tracing
        pass

    # Or use the tracer directly
    tracer = get_tracer()
    with tracer.trace("memory_store", {"content": "..."}) as ctx:
        # Do work
        ctx.add_event("sqlite_write", {"doc_id": doc_id})
"""

import functools
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from threading import Lock

logger = logging.getLogger("memory_mcp.tracer")


@dataclass
class TraceEvent:
    """A single event within a trace."""
    name: str
    timestamp: float
    duration_ms: Optional[float] = None
    data: Dict[str, Any] = field(default_factory=dict)
    tier: Optional[str] = None  # "hot", "warm", "cold", "archive"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        result = {
            "name": self.name,
            "timestamp": self.timestamp,
        }
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.data:
            result["data"] = self.data
        if self.tier:
            result["tier"] = self.tier
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class TraceContext:
    """Context for a single request trace."""
    request_id: str
    tool_name: str
    arguments: Dict[str, Any]
    start_time: float
    events: List[TraceEvent] = field(default_factory=list)
    end_time: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[str] = None

    def add_event(
        self,
        name: str,
        data: Optional[Dict[str, Any]] = None,
        tier: Optional[str] = None
    ) -> None:
        """Add an event to the trace."""
        event = TraceEvent(
            name=name,
            timestamp=time.time(),
            data=data or {},
            tier=tier
        )
        self.events.append(event)

    def start_span(self, name: str, tier: Optional[str] = None) -> "SpanContext":
        """Start a timed span within the trace."""
        return SpanContext(self, name, tier)

    @property
    def duration_ms(self) -> Optional[float]:
        """Total request duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary."""
        result = {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "arguments": _sanitize_arguments(self.arguments),
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "events": [e.to_dict() for e in self.events],
        }
        if self.end_time:
            result["end_time"] = datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat()
            result["duration_ms"] = self.duration_ms
        if self.result is not None:
            result["success"] = True
        if self.error:
            result["success"] = False
            result["error"] = self.error
            result["error_type"] = self.error_type
        return result


class SpanContext:
    """Context manager for timed spans within a trace."""

    def __init__(self, trace: TraceContext, name: str, tier: Optional[str] = None):
        self.trace = trace
        self.name = name
        self.tier = tier
        self.start_time: float = 0
        self._data: Dict[str, Any] = {}

    def __enter__(self) -> "SpanContext":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        event = TraceEvent(
            name=self.name,
            timestamp=self.start_time,
            duration_ms=round(duration_ms, 3),
            data=self._data,
            tier=self.tier,
            error=str(exc_val) if exc_val else None
        )
        self.trace.events.append(event)
        return False  # Don't suppress exceptions

    def add_data(self, **kwargs):
        """Add data to the span."""
        self._data.update(kwargs)


def _sanitize_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize arguments for logging (truncate large content)."""
    result = {}
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 200:
            result[key] = value[:200] + f"... ({len(value)} chars)"
        elif isinstance(value, (list, dict)) and len(str(value)) > 500:
            result[key] = f"<{type(value).__name__} with {len(value)} items>"
        else:
            result[key] = value
    return result


class RequestTracer:
    """Central request tracing facility."""

    def __init__(
        self,
        log_file: Optional[str] = None,
        max_traces: int = 1000,
        enabled: bool = True
    ):
        self.enabled = enabled
        self.max_traces = max_traces
        self.traces: List[TraceContext] = []
        self._lock = Lock()
        self._current_trace: Optional[TraceContext] = None

        # Set up file logging if path provided
        self.log_file = log_file
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def start_trace(self, tool_name: str, arguments: Dict[str, Any]) -> TraceContext:
        """Start a new trace for a request."""
        trace = TraceContext(
            request_id=str(uuid.uuid4())[:8],
            tool_name=tool_name,
            arguments=arguments,
            start_time=time.time()
        )
        self._current_trace = trace
        return trace

    def end_trace(self, trace: TraceContext, result: Any = None, error: Optional[Exception] = None):
        """End a trace and record the result."""
        trace.end_time = time.time()

        if error:
            trace.error = str(error)
            trace.error_type = type(error).__name__
        else:
            trace.result = result

        # Store trace
        with self._lock:
            self.traces.append(trace)
            # Trim old traces
            if len(self.traces) > self.max_traces:
                self.traces = self.traces[-self.max_traces:]

        # Write to log file if configured
        if self.log_file:
            self._write_trace(trace)

        self._current_trace = None
        return trace

    def _write_trace(self, trace: TraceContext):
        """Write trace to log file as JSON line."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write trace to file: {e}")

    @contextmanager
    def trace(self, tool_name: str, arguments: Dict[str, Any]):
        """Context manager for tracing a request."""
        if not self.enabled:
            yield None
            return

        trace = self.start_trace(tool_name, arguments)
        try:
            yield trace
            self.end_trace(trace, result=True)
        except Exception as e:
            self.end_trace(trace, error=e)
            raise

    @property
    def current_trace(self) -> Optional[TraceContext]:
        """Get the current active trace."""
        return self._current_trace

    def get_recent_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent traces as dictionaries."""
        with self._lock:
            recent = self.traces[-limit:]
            return [t.to_dict() for t in recent]

    def get_trace_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trace by request ID."""
        with self._lock:
            for trace in reversed(self.traces):
                if trace.request_id == request_id:
                    return trace.to_dict()
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        with self._lock:
            if not self.traces:
                return {
                    "total_traces": 0,
                    "enabled": self.enabled
                }

            durations = [t.duration_ms for t in self.traces if t.duration_ms]
            errors = [t for t in self.traces if t.error]

            tools_count: Dict[str, int] = {}
            for t in self.traces:
                tools_count[t.tool_name] = tools_count.get(t.tool_name, 0) + 1

            return {
                "total_traces": len(self.traces),
                "error_count": len(errors),
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "tools_breakdown": tools_count,
                "enabled": self.enabled
            }

    def clear(self):
        """Clear all stored traces."""
        with self._lock:
            self.traces.clear()


# Global tracer instance
_tracer: Optional[RequestTracer] = None


def get_tracer() -> RequestTracer:
    """Get or create the global tracer instance."""
    global _tracer
    if _tracer is None:
        # Check for environment configuration
        log_file = os.environ.get("MEMORY_MCP_TRACE_FILE")
        enabled = os.environ.get("MEMORY_MCP_TRACE_ENABLED", "true").lower() != "false"
        _tracer = RequestTracer(log_file=log_file, enabled=enabled)
    return _tracer


def set_tracer(tracer: RequestTracer):
    """Set the global tracer instance."""
    global _tracer
    _tracer = tracer


F = TypeVar('F', bound=Callable[..., Any])


def trace_request(func: F) -> F:
    """Decorator to trace a tool handler function.

    Usage:
        @trace_request
        def handle_memory_store(self, arguments: dict) -> dict:
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracer = get_tracer()
        if not tracer.enabled:
            return func(*args, **kwargs)

        # Extract tool name from function name
        tool_name = func.__name__
        if tool_name.startswith("_tool_"):
            tool_name = tool_name[6:]  # Remove _tool_ prefix

        # Extract arguments (assume first positional arg after self is arguments dict)
        arguments = {}
        if len(args) >= 2:
            arguments = args[1] if isinstance(args[1], dict) else {}
        elif "arguments" in kwargs:
            arguments = kwargs["arguments"]

        trace = tracer.start_trace(tool_name, arguments)
        try:
            result = func(*args, **kwargs)
            tracer.end_trace(trace, result=result)
            return result
        except Exception as e:
            tracer.end_trace(trace, error=e)
            raise

    return wrapper  # type: ignore


# Convenience functions for adding events to current trace
def trace_event(name: str, data: Optional[Dict[str, Any]] = None, tier: Optional[str] = None):
    """Add an event to the current trace (if active)."""
    tracer = get_tracer()
    if tracer.current_trace:
        tracer.current_trace.add_event(name, data, tier)


def trace_span(name: str, tier: Optional[str] = None) -> SpanContext:
    """Start a span in the current trace (if active).

    Usage:
        with trace_span("sqlite_query", tier="cold") as span:
            span.add_data(rows=10)
            # do work
    """
    tracer = get_tracer()
    if tracer.current_trace:
        return tracer.current_trace.start_span(name, tier)

    # Return a no-op context if no active trace
    class NoOpSpan:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def add_data(self, **kwargs):
            pass

    return NoOpSpan()  # type: ignore
