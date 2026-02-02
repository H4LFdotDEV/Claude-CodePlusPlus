# server.py
# Memory MCP Server for Claude Code++
# Jeremiah Kroesche | Halfservers LLC
#
# MCP protocol server exposing memory operations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Optional, Dict, Any

from .config import get_config, MemoryConfig, set_config
from .sqlite_index import SQLiteIndex
from .vault_manager import VaultManager
from .redis_client import RedisClient, REDIS_AVAILABLE
from .embedding_provider import get_embedding_provider
from .tool_schemas import get_tool_schemas
from .handlers import MemoryHandler, SessionHandler, VaultHandler, StatsHandler, ResearchHandler, TierHandler, ProactiveHandler
from .graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE
from .livegrep_client import LivegrepClient, HTTPX_AVAILABLE
from .tier_manager import TierManager
from .rate_limiter import RateLimiter

# Configure logging
LOG_LEVEL = os.environ.get("MEMORY_MCP_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("MEMORY_MCP_LOG_FILE", None)

# Create logger
logger = logging.getLogger("memory_mcp")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Console handler (only for non-stdio mode to avoid protocol interference)
if not sys.stdin.isatty() or LOG_FILE:
    # In stdio mode, only log to file if specified
    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
else:
    # Interactive mode - log to stderr (not stdout which is for MCP responses)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)


class MemoryMCPServer:
    """MCP Server for the Claude Code++ memory system."""

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or get_config()
        set_config(self.config)

        # Initialize core components
        self.sqlite = SQLiteIndex()
        self.vault = VaultManager()

        # Optional components (may not be available)
        self.redis: Optional[RedisClient] = None
        self.embedder = None
        self.graphiti: Optional[GraphitiManager] = None
        self.livegrep: Optional[LivegrepClient] = None
        self.tier_manager: Optional[TierManager] = None

        self._init_optional_components()

        # MCP state
        self._request_id = 0
        self._session_id = str(uuid.uuid4())

        # Rate limiting
        self._rate_limiter = RateLimiter()
        logger.info(
            f"Rate limiter initialized: {self._rate_limiter.max_requests} requests/"
            f"{self._rate_limiter.window_seconds}s"
        )

        # Initialize handlers with shared dependencies
        self._init_handlers()

    def _init_optional_components(self):
        """Initialize optional components with graceful degradation."""
        # Redis (hot cache)
        if REDIS_AVAILABLE:
            try:
                self.redis = RedisClient()
                if not self.redis.connect():
                    logger.warning("Redis connection failed - running without hot cache")
                    self.redis = None
                else:
                    logger.info("Redis connected successfully")
            except Exception as e:
                logger.warning(f"Redis initialization failed: {e}")
                self.redis = None
        else:
            logger.info("Redis not available - install with: pip install redis")

        # Embeddings
        try:
            self.embedder = get_embedding_provider()
            logger.info(f"Embedding provider: {self.embedder.name}")
        except Exception as e:
            logger.warning(f"Embedding provider initialization failed: {e}")
            self.embedder = None

        # Graphiti (warm tier - knowledge graph)
        if GRAPHITI_AVAILABLE:
            try:
                self.graphiti = GraphitiManager()
                # Note: Graphiti is async, full initialization happens on first use
                logger.info("Graphiti manager initialized (lazy connection)")
            except Exception as e:
                logger.warning(f"Graphiti initialization failed: {e}")
                self.graphiti = None
        else:
            logger.info("Graphiti not available - install with: pip install graphiti-core")

        # livegrep (cold tier - code search)
        if HTTPX_AVAILABLE:
            try:
                self.livegrep = LivegrepClient()
                if self.livegrep.health_check():
                    logger.info("livegrep client connected")
                else:
                    logger.info("livegrep server not responding - code search disabled")
                    self.livegrep = None
            except Exception as e:
                logger.warning(f"livegrep initialization failed: {e}")
                self.livegrep = None
        else:
            logger.info("httpx not available for livegrep - install with: pip install httpx")

        # TierManager (orchestrates all tiers)
        self.tier_manager = TierManager(
            redis=self.redis,
            graphiti=self.graphiti,
            livegrep=self.livegrep,
            sqlite=self.sqlite
        )
        logger.info("TierManager initialized")

    def _init_handlers(self):
        """Initialize tool handlers with shared dependencies."""
        handler_kwargs = {
            "sqlite": self.sqlite,
            "vault": self.vault,
            "redis": self.redis,
            "embedder": self.embedder,
            "tier_manager": self.tier_manager,
            "rate_limiter": self._rate_limiter,
            "session_id": self._session_id
        }

        self._memory_handler = MemoryHandler(**handler_kwargs)
        self._session_handler = SessionHandler(**handler_kwargs)
        self._vault_handler = VaultHandler(**handler_kwargs)
        self._stats_handler = StatsHandler(**handler_kwargs)
        self._research_handler = ResearchHandler(**handler_kwargs)
        self._tier_handler = TierHandler(**handler_kwargs)
        self._proactive_handler = ProactiveHandler(**handler_kwargs)

    # MCP Protocol Methods

    def _create_response(self, result: Any, request_id: int) -> Dict:
        """Create MCP JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    def _create_error(self, code: int, message: str, request_id: int) -> Dict:
        """Create MCP JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message}
        }

    def handle_initialize(self, params: Dict) -> Dict:
        """Handle MCP initialize request."""
        # Echo back the client's protocol version for compatibility
        client_version = params.get("protocolVersion", "2024-11-05")
        return {
            "protocolVersion": client_version,
            "serverInfo": {
                "name": "claude-code-pp-memory",
                "version": "1.0.0"
            },
            "capabilities": {
                "tools": {},
                "resources": {}
            }
        }

    def handle_list_tools(self) -> Dict:
        """List available MCP tools."""
        tools = get_tool_schemas()
        return {"tools": tools}

    def handle_call_tool(self, name: str, arguments: Dict) -> Dict:
        """Handle tool invocation by delegating to appropriate handler."""
        # Map tool names to handler methods
        tool_dispatch = {
            "memory_store": self._memory_handler.store,
            "memory_search": self._memory_handler.search,
            "memory_recall": self._memory_handler.recall,
            "memory_delete": self._memory_handler.delete,
            "memory_list": self._memory_handler.list,
            "session_save": self._session_handler.save,
            "session_restore": self._session_handler.restore,
            "vault_write": self._vault_handler.write,
            "vault_read": self._vault_handler.read,
            "memory_stats": self._stats_handler.get_stats,
            # Research tools
            "research_session_start": self._research_handler.session_start,
            "research_session_end": self._research_handler.session_end,
            "research_transcript_store": self._research_handler.transcript_store,
            "research_capture_store": self._research_handler.capture_store,
            "research_search": self._research_handler.search,
            # Tier-specific tools (knowledge graph and code search)
            "search_entities": self._tier_handler.search_entities,
            "search_facts": self._tier_handler.search_facts,
            "code_search": self._tier_handler.code_search,
            "search_function": self._tier_handler.search_function,
            "search_class": self._tier_handler.search_class,
            # Proactive tools (memU-inspired continuous learning)
            "proactive_status": self._handle_proactive_status,
            "extract_insights": self._handle_extract_insights,
            "configure_proactive": self._handle_configure_proactive,
        }

        handler = tool_dispatch.get(name)
        if not handler:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        try:
            logger.debug(f"Calling tool: {name} with args: {list(arguments.keys())}")
            result = handler(arguments)

            # Sync session ID changes from handlers back to server
            if name == "session_restore":
                self._session_id = self._session_handler.session_id

            logger.debug(f"Tool {name} completed successfully")
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        except (ValueError, TypeError) as e:
            logger.warning(f"Validation error in {name}: {e}")
            return {"content": [{"type": "text", "text": f"Validation error: {str(e)}"}], "isError": True}
        except Exception as e:
            logger.error(f"Error in tool {name}: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}

    # Proactive tool wrappers (async handlers need sync wrappers)

    def _handle_proactive_status(self, arguments: Dict) -> Dict:
        """Sync wrapper for proactive_status."""
        from .async_utils import run_async
        return run_async(
            self._proactive_handler.handle_proactive_status(
                include_recent=arguments.get("include_recent", True),
                limit=arguments.get("limit", 10),
            )
        )

    def _handle_extract_insights(self, arguments: Dict) -> Dict:
        """Sync wrapper for extract_insights."""
        from .async_utils import run_async
        return run_async(
            self._proactive_handler.handle_extract_insights(
                text=arguments.get("text", ""),
                context=arguments.get("context"),
                immediate=arguments.get("immediate", True),
            )
        )

    def _handle_configure_proactive(self, arguments: Dict) -> Dict:
        """Sync wrapper for configure_proactive."""
        from .async_utils import run_async
        return run_async(
            self._proactive_handler.handle_configure_proactive(
                min_confidence=arguments.get("min_confidence"),
                enabled=arguments.get("enabled"),
                queue_enabled=arguments.get("queue_enabled"),
            )
        )

    # MCP Server Loop

    async def run_stdio(self):
        """Run MCP server over stdio."""
        loop = asyncio.get_running_loop()

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                request = json.loads(line.decode())
                logger.info(f"REQUEST: {json.dumps(request)}")

                # Notifications don't have an "id" and don't get responses
                if "id" not in request:
                    # Handle notification silently (no response)
                    logger.info(f"NOTIFICATION (no response): {request.get('method')}")
                    self._handle_notification(request)
                    continue

                response = self._handle_request(request)
                response_line = json.dumps(response) + "\n"
                logger.info(f"RESPONSE: {response_line[:500]}")
                writer.write(response_line.encode())
                await writer.drain()

            except json.JSONDecodeError:
                continue
            except ConnectionResetError:
                # Connection closed by client - normal shutdown
                logger.info("Connection closed by client")
                break
            except BrokenPipeError:
                # Pipe closed - normal shutdown
                logger.info("Pipe closed")
                break
            except Exception as e:
                logger.error(f"Error handling request: {e}")
                try:
                    error_response = self._create_error(-32603, str(e), 0)
                    writer.write((json.dumps(error_response) + "\n").encode())
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    # Connection already closed, can't send error
                    break

    def _handle_notification(self, request: Dict) -> None:
        """Handle incoming MCP notification (no response needed)."""
        method = request.get("method", "")
        # Notifications are fire-and-forget, just log them
        if method == "notifications/initialized":
            pass  # Client is ready, nothing to do
        elif method == "notifications/cancelled":
            pass  # Request was cancelled
        # Add other notification handlers as needed

    def _handle_request(self, request: Dict) -> Dict:
        """Handle incoming MCP request."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id", 0)

        # Apply rate limiting (use session_id as client identifier)
        # Skip rate limiting for initialize to allow connection setup
        if method != "initialize":
            rate_result = self._rate_limiter.check(self._session_id)
            if not rate_result.allowed:
                logger.warning(
                    f"Rate limit exceeded for session {self._session_id}: "
                    f"{rate_result.current_count}/{rate_result.limit} requests"
                )
                return self._create_error(
                    -32000,
                    f"Rate limit exceeded: {rate_result.current_count}/{rate_result.limit} "
                    f"requests in {rate_result.window_seconds}s. "
                    f"Retry after {rate_result.retry_after:.1f}s",
                    request_id
                )

        if method == "initialize":
            return self._create_response(self.handle_initialize(params), request_id)
        elif method == "tools/list":
            return self._create_response(self.handle_list_tools(), request_id)
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self._create_response(self.handle_call_tool(name, arguments), request_id)
        elif method == "resources/list":
            # Return empty resources list
            return self._create_response({"resources": []}, request_id)
        elif method == "resources/read":
            # No resources to read
            return self._create_error(-32602, "Resource not found", request_id)
        else:
            return self._create_error(-32601, f"Unknown method: {method}", request_id)


def main():
    """Entry point for the MCP server."""
    server = MemoryMCPServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
