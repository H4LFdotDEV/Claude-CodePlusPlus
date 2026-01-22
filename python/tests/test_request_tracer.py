"""
Tests for the Request Tracing System.

Tests request tracing capabilities including:
- Request ID generation
- Event logging
- Span timing
- Trace storage and retrieval
- Decorator functionality
"""

import json
import os
import tempfile
import time
import pytest
from pathlib import Path

from memory_mcp.request_tracer import (
    RequestTracer,
    TraceContext,
    TraceEvent,
    SpanContext,
    trace_request,
    trace_event,
    trace_span,
    get_tracer,
    set_tracer,
    _sanitize_arguments,
)


class TestTraceEvent:
    """Test TraceEvent dataclass."""

    def test_event_to_dict_basic(self):
        """Test basic event serialization."""
        event = TraceEvent(
            name="test_event",
            timestamp=1000.0,
        )
        result = event.to_dict()

        assert result["name"] == "test_event"
        assert result["timestamp"] == 1000.0
        assert "duration_ms" not in result
        assert "data" not in result

    def test_event_to_dict_with_all_fields(self):
        """Test event serialization with all fields."""
        event = TraceEvent(
            name="query",
            timestamp=1000.0,
            duration_ms=5.5,
            data={"rows": 10},
            tier="cold",
            error="timeout"
        )
        result = event.to_dict()

        assert result["name"] == "query"
        assert result["duration_ms"] == 5.5
        assert result["data"] == {"rows": 10}
        assert result["tier"] == "cold"
        assert result["error"] == "timeout"


class TestTraceContext:
    """Test TraceContext class."""

    def test_context_creation(self):
        """Test trace context creation."""
        ctx = TraceContext(
            request_id="abc123",
            tool_name="memory_store",
            arguments={"content": "test"},
            start_time=time.time()
        )

        assert ctx.request_id == "abc123"
        assert ctx.tool_name == "memory_store"
        assert ctx.events == []

    def test_add_event(self):
        """Test adding events to context."""
        ctx = TraceContext(
            request_id="abc123",
            tool_name="memory_store",
            arguments={},
            start_time=time.time()
        )

        ctx.add_event("sqlite_write", {"doc_id": "doc-1"}, tier="cold")

        assert len(ctx.events) == 1
        assert ctx.events[0].name == "sqlite_write"
        assert ctx.events[0].tier == "cold"

    def test_duration_calculation(self):
        """Test duration is calculated correctly."""
        ctx = TraceContext(
            request_id="abc123",
            tool_name="test",
            arguments={},
            start_time=1000.0
        )
        ctx.end_time = 1000.050  # 50ms later

        assert abs(ctx.duration_ms - 50.0) < 0.01

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = TraceContext(
            request_id="abc123",
            tool_name="memory_store",
            arguments={"type": "note"},
            start_time=1000.0
        )
        ctx.end_time = 1000.100
        ctx.result = True

        result = ctx.to_dict()

        assert result["request_id"] == "abc123"
        assert result["tool_name"] == "memory_store"
        assert result["arguments"] == {"type": "note"}
        assert "start_time" in result
        assert "end_time" in result
        assert abs(result["duration_ms"] - 100.0) < 0.01
        assert result["success"] is True


class TestSpanContext:
    """Test SpanContext for timed operations."""

    def test_span_measures_duration(self):
        """Test span measures execution time."""
        trace = TraceContext(
            request_id="abc",
            tool_name="test",
            arguments={},
            start_time=time.time()
        )

        with trace.start_span("operation", tier="hot") as span:
            time.sleep(0.01)  # 10ms

        assert len(trace.events) == 1
        assert trace.events[0].name == "operation"
        assert trace.events[0].tier == "hot"
        assert trace.events[0].duration_ms >= 10  # At least 10ms

    def test_span_add_data(self):
        """Test adding data to span."""
        trace = TraceContext(
            request_id="abc",
            tool_name="test",
            arguments={},
            start_time=time.time()
        )

        with trace.start_span("query") as span:
            span.add_data(rows=5, cached=True)

        assert trace.events[0].data == {"rows": 5, "cached": True}

    def test_span_captures_error(self):
        """Test span captures exceptions."""
        trace = TraceContext(
            request_id="abc",
            tool_name="test",
            arguments={},
            start_time=time.time()
        )

        with pytest.raises(ValueError):
            with trace.start_span("failing") as span:
                raise ValueError("test error")

        assert trace.events[0].error == "test error"


class TestRequestTracer:
    """Test the RequestTracer class."""

    def test_tracer_creation(self):
        """Test tracer creation with defaults."""
        tracer = RequestTracer()

        assert tracer.enabled is True
        assert tracer.max_traces == 1000
        assert tracer.traces == []

    def test_start_trace(self):
        """Test starting a new trace."""
        tracer = RequestTracer()
        trace = tracer.start_trace("memory_store", {"content": "test"})

        assert trace.tool_name == "memory_store"
        assert len(trace.request_id) == 8
        assert tracer.current_trace is trace

    def test_end_trace_success(self):
        """Test ending a trace with success."""
        tracer = RequestTracer()
        trace = tracer.start_trace("memory_store", {})
        tracer.end_trace(trace, result={"id": "doc-1"})

        assert trace.end_time is not None
        assert trace.result == {"id": "doc-1"}
        assert trace.error is None
        assert len(tracer.traces) == 1

    def test_end_trace_error(self):
        """Test ending a trace with error."""
        tracer = RequestTracer()
        trace = tracer.start_trace("memory_store", {})
        tracer.end_trace(trace, error=ValueError("test error"))

        assert trace.error == "test error"
        assert trace.error_type == "ValueError"
        assert trace.result is None

    def test_trace_context_manager(self):
        """Test trace as context manager."""
        tracer = RequestTracer()

        with tracer.trace("memory_search", {"query": "test"}) as trace:
            trace.add_event("search_start")

        assert len(tracer.traces) == 1
        assert len(tracer.traces[0].events) == 1

    def test_trace_context_manager_error(self):
        """Test trace captures error from context manager."""
        tracer = RequestTracer()

        with pytest.raises(RuntimeError):
            with tracer.trace("memory_store", {}) as trace:
                raise RuntimeError("test failure")

        assert tracer.traces[0].error == "test failure"

    def test_max_traces_limit(self):
        """Test trace storage respects max_traces limit."""
        tracer = RequestTracer(max_traces=5)

        for i in range(10):
            trace = tracer.start_trace(f"tool_{i}", {})
            tracer.end_trace(trace)

        assert len(tracer.traces) == 5
        # Should keep the most recent
        assert tracer.traces[-1].tool_name == "tool_9"

    def test_get_recent_traces(self):
        """Test retrieving recent traces."""
        tracer = RequestTracer()

        for i in range(5):
            trace = tracer.start_trace(f"tool_{i}", {})
            tracer.end_trace(trace)

        recent = tracer.get_recent_traces(limit=3)

        assert len(recent) == 3
        assert recent[-1]["tool_name"] == "tool_4"

    def test_get_trace_by_id(self):
        """Test retrieving trace by ID."""
        tracer = RequestTracer()
        trace = tracer.start_trace("test", {})
        request_id = trace.request_id
        tracer.end_trace(trace)

        result = tracer.get_trace_by_id(request_id)

        assert result is not None
        assert result["request_id"] == request_id

    def test_get_stats(self):
        """Test getting tracer statistics."""
        tracer = RequestTracer()

        # Add some traces
        trace1 = tracer.start_trace("memory_store", {})
        time.sleep(0.01)
        tracer.end_trace(trace1)

        trace2 = tracer.start_trace("memory_search", {})
        tracer.end_trace(trace2, error=ValueError("test"))

        stats = tracer.get_stats()

        assert stats["total_traces"] == 2
        assert stats["error_count"] == 1
        assert stats["avg_duration_ms"] > 0
        assert "memory_store" in stats["tools_breakdown"]

    def test_tracer_disabled(self):
        """Test tracer when disabled."""
        tracer = RequestTracer(enabled=False)

        with tracer.trace("test", {}) as trace:
            assert trace is None

        assert len(tracer.traces) == 0


class TestTracerFileLogging:
    """Test trace file logging functionality."""

    def test_write_trace_to_file(self):
        """Test traces are written to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "traces.jsonl")
            tracer = RequestTracer(log_file=log_file)

            with tracer.trace("memory_store", {"type": "note"}) as trace:
                trace.add_event("write")

            # Verify file contents
            assert os.path.exists(log_file)
            with open(log_file) as f:
                line = f.readline()
                data = json.loads(line)
                assert data["tool_name"] == "memory_store"


class TestTraceDecorator:
    """Test the @trace_request decorator."""

    def test_decorator_traces_function(self):
        """Test decorator traces function calls."""
        tracer = RequestTracer()
        set_tracer(tracer)

        @trace_request
        def my_tool(self, arguments):
            return {"result": "ok"}

        result = my_tool(None, {"key": "value"})

        assert result == {"result": "ok"}
        assert len(tracer.traces) == 1
        assert tracer.traces[0].tool_name == "my_tool"

    def test_decorator_captures_error(self):
        """Test decorator captures exceptions."""
        tracer = RequestTracer()
        set_tracer(tracer)

        @trace_request
        def failing_tool(self, arguments):
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_tool(None, {})

        assert tracer.traces[0].error == "test error"

    def test_decorator_strips_tool_prefix(self):
        """Test decorator strips _tool_ prefix from function names."""
        tracer = RequestTracer()
        set_tracer(tracer)

        @trace_request
        def _tool_memory_store(self, arguments):
            return {}

        _tool_memory_store(None, {})

        assert tracer.traces[0].tool_name == "memory_store"


class TestConvenienceFunctions:
    """Test trace_event and trace_span convenience functions."""

    def test_trace_event_in_active_trace(self):
        """Test adding event to active trace."""
        tracer = RequestTracer()
        set_tracer(tracer)

        with tracer.trace("test", {}) as trace:
            trace_event("sub_operation", {"count": 5}, tier="hot")

        assert len(tracer.traces[0].events) == 1
        assert tracer.traces[0].events[0].name == "sub_operation"

    def test_trace_event_no_active_trace(self):
        """Test trace_event does nothing without active trace."""
        tracer = RequestTracer()
        set_tracer(tracer)

        # Should not raise
        trace_event("orphan_event", {})

    def test_trace_span_in_active_trace(self):
        """Test using trace_span in active trace."""
        tracer = RequestTracer()
        set_tracer(tracer)

        with tracer.trace("test", {}) as trace:
            with trace_span("sub_span", tier="cold") as span:
                span.add_data(processed=True)

        assert len(tracer.traces[0].events) == 1
        assert tracer.traces[0].events[0].data["processed"] is True

    def test_trace_span_no_active_trace(self):
        """Test trace_span returns no-op without active trace."""
        tracer = RequestTracer()
        set_tracer(tracer)

        # Should not raise
        with trace_span("orphan_span") as span:
            span.add_data(value=1)


class TestSanitizeArguments:
    """Test argument sanitization for logging."""

    def test_sanitize_short_string(self):
        """Test short strings are not truncated."""
        result = _sanitize_arguments({"content": "short"})
        assert result["content"] == "short"

    def test_sanitize_long_string(self):
        """Test long strings are truncated."""
        long_content = "x" * 500
        result = _sanitize_arguments({"content": long_content})

        assert len(result["content"]) < len(long_content)
        assert "500 chars" in result["content"]

    def test_sanitize_large_list(self):
        """Test large lists are summarized."""
        large_list = list(range(1000))
        result = _sanitize_arguments({"items": large_list})

        assert "<list with 1000 items>" in result["items"]

    def test_sanitize_preserves_simple_values(self):
        """Test simple values are preserved."""
        result = _sanitize_arguments({
            "count": 10,
            "enabled": True,
            "name": "test"
        })

        assert result["count"] == 10
        assert result["enabled"] is True
        assert result["name"] == "test"
