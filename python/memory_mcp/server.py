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

# Lazy initialization support
import threading
from typing import TypeVar, Generic, Callable

T = TypeVar("T")


def _sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages to avoid leaking sensitive information.

    Removes file paths, stack traces, and internal details from error messages.
    Full details are logged server-side for debugging.
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Remove file paths (Unix and Windows)
    import re
    # Unix paths
    error_msg = re.sub(r'/[\w./-]+\.py', '<file>', error_msg)
    error_msg = re.sub(r'/[\w./-]+/', '<path>/', error_msg)
    # Windows paths
    error_msg = re.sub(r'[A-Z]:\\[\w.\\-]+\.py', '<file>', error_msg)
    error_msg = re.sub(r'[A-Z]:\\[\w.\\-]+\\', '<path>\\', error_msg)
    # Home directory references
    error_msg = re.sub(r'/Users/\w+', '<home>', error_msg)
    error_msg = re.sub(r'/home/\w+', '<home>', error_msg)
    error_msg = re.sub(r'C:\\Users\\\w+', '<home>', error_msg)

    # Truncate very long messages (may contain stack traces)
    if len(error_msg) > 200:
        error_msg = error_msg[:200] + "..."

    # Map specific internal errors to user-friendly messages
    if "Connection refused" in error_msg:
        return "Service connection failed. Please check infrastructure status."
    if "Permission denied" in error_msg:
        return "Access denied. Check file permissions."
    if "No such file or directory" in error_msg:
        return "Resource not found."
    if "SQLite" in error_type or "sqlite" in error_msg.lower():
        return "Database operation failed. Please try again."
    if "Redis" in error_type or "redis" in error_msg.lower():
        return "Cache operation failed. Please try again."

    # Return sanitized message with error type
    return f"{error_type}: {error_msg}"


class LazyService(Generic[T]):
    """Thread-safe lazy initialization wrapper for services.

    Services are initialized on first access, reducing startup time.
    Once initialized, subsequent accesses return the cached instance.
    """

    def __init__(self, factory: Callable[[], T], name: str = "service"):
        self._factory = factory
        self._name = name
        self._instance: Optional[T] = None
        self._lock = threading.Lock()
        self._init_attempted = False
        self._init_error: Optional[Exception] = None

    def get(self) -> Optional[T]:
        """Get the service instance, initializing on first access.

        Thread-safe double-checked locking pattern:
        1. Fast path: if already initialized, return immediately (no lock)
        2. Slow path: acquire lock, check again, initialize if needed
        """
        # Fast path: already initialized (no lock needed)
        instance = self._instance
        if instance is not None:
            return instance

        # Slow path: need to check/initialize under lock
        with self._lock:
            # Double-check after acquiring lock (another thread may have initialized)
            if self._instance is not None:
                return self._instance

            # Check if we already tried and failed (must be inside lock)
            if self._init_attempted:
                return None

            try:
                logger.debug(f"Lazy initializing {self._name}...")
                self._instance = self._factory()
                logger.info(f"Lazy initialized {self._name}")
            except Exception as e:
                logger.warning(f"Lazy initialization of {self._name} failed: {e}")
                self._init_error = e
            finally:
                self._init_attempted = True

            return self._instance

    @property
    def initialized(self) -> bool:
        """Check if the service has been initialized."""
        return self._instance is not None

    @property
    def available(self) -> bool:
        """Check if the service is available (initialized and not None)."""
        return self._instance is not None

    def reset(self) -> None:
        """Reset the lazy service to allow re-initialization."""
        with self._lock:
            self._instance = None
            self._init_attempted = False
            self._init_error = None


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
    """MCP Server for the Claude Code++ memory system.

    Uses lazy initialization for optional components to reduce startup time.
    Core components (sqlite, vault) are initialized immediately as they're lightweight.
    Optional components (redis, graphiti, livegrep) are initialized on first use.
    """

    def __init__(self, config: Optional[MemoryConfig] = None, eager_init: bool = False):
        """Initialize the MCP server.

        Args:
            config: Optional memory configuration
            eager_init: If True, initialize all components immediately (for testing)
        """
        self.config = config or get_config()
        set_config(self.config)

        # Core components (lightweight, always initialized)
        self.sqlite = SQLiteIndex()
        self.vault = VaultManager()

        # Lazy services for optional components
        self._lazy_redis = LazyService(self._create_redis, "Redis")
        self._lazy_embedder = LazyService(self._create_embedder, "Embedder")
        self._lazy_graphiti = LazyService(self._create_graphiti, "Graphiti")
        self._lazy_livegrep = LazyService(self._create_livegrep, "livegrep")

        # TierManager is created lazily but needs lazy services
        self._lazy_tier_manager = LazyService(self._create_tier_manager, "TierManager")

        # MCP state
        self._request_id = 0
        self._session_id = str(uuid.uuid4())

        # Rate limiting (lightweight, always initialized)
        self._rate_limiter = RateLimiter()
        logger.info(
            f"Rate limiter initialized: {self._rate_limiter.max_requests} requests/"
            f"{self._rate_limiter.window_seconds}s"
        )

        # Handlers are initialized lazily on first tool call
        self._handlers_initialized = False
        self._memory_handler = None
        self._session_handler = None
        self._vault_handler = None
        self._stats_handler = None
        self._research_handler = None
        self._tier_handler = None
        self._proactive_handler = None

        # Optionally eagerly initialize everything (for testing/compatibility)
        if eager_init:
            self._ensure_handlers_initialized()
            logger.info("Eager initialization completed")
        else:
            logger.info("Server initialized with lazy loading (startup optimized)")

    # Lazy service factory methods

    def _create_redis(self) -> Optional[RedisClient]:
        """Factory for Redis client."""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available - install with: pip install redis")
            return None
        try:
            client = RedisClient()
            if not client.connect():
                logger.warning("Redis connection failed - running without hot cache")
                return None
            logger.info("Redis connected successfully")
            return client
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}")
            return None

    def _create_embedder(self):
        """Factory for embedding provider."""
        try:
            embedder = get_embedding_provider()
            logger.info(f"Embedding provider: {embedder.name}")
            return embedder
        except Exception as e:
            logger.warning(f"Embedding provider initialization failed: {e}")
            return None

    def _create_graphiti(self) -> Optional[GraphitiManager]:
        """Factory for Graphiti manager."""
        if not GRAPHITI_AVAILABLE:
            logger.info("Graphiti not available - install with: pip install graphiti-core")
            return None
        try:
            manager = GraphitiManager()
            logger.info("Graphiti manager initialized (lazy connection)")
            return manager
        except Exception as e:
            logger.warning(f"Graphiti initialization failed: {e}")
            return None

    def _create_livegrep(self) -> Optional[LivegrepClient]:
        """Factory for livegrep client."""
        if not HTTPX_AVAILABLE:
            logger.info("httpx not available for livegrep - install with: pip install httpx")
            return None
        try:
            client = LivegrepClient()
            if client.health_check():
                logger.info("livegrep client connected")
                return client
            else:
                logger.info("livegrep server not responding - code search disabled")
                return None
        except Exception as e:
            logger.warning(f"livegrep initialization failed: {e}")
            return None

    def _create_tier_manager(self) -> TierManager:
        """Factory for TierManager."""
        return TierManager(
            redis=self.redis,
            graphiti=self.graphiti,
            livegrep=self.livegrep,
            sqlite=self.sqlite
        )

    # Properties for accessing lazy services

    @property
    def redis(self) -> Optional[RedisClient]:
        """Get Redis client (lazy initialized)."""
        return self._lazy_redis.get()

    @property
    def embedder(self):
        """Get embedding provider (lazy initialized)."""
        return self._lazy_embedder.get()

    @property
    def graphiti(self) -> Optional[GraphitiManager]:
        """Get Graphiti manager (lazy initialized)."""
        return self._lazy_graphiti.get()

    @property
    def livegrep(self) -> Optional[LivegrepClient]:
        """Get livegrep client (lazy initialized)."""
        return self._lazy_livegrep.get()

    @property
    def tier_manager(self) -> Optional[TierManager]:
        """Get TierManager (lazy initialized)."""
        return self._lazy_tier_manager.get()

    def _ensure_handlers_initialized(self):
        """Initialize handlers on first use."""
        if self._handlers_initialized:
            return

        self._init_handlers()
        self._handlers_initialized = True

    def _init_handlers(self):
        """Initialize tool handlers with shared dependencies (lazy)."""
        handler_kwargs = {
            "sqlite": self.sqlite,
            "vault": self.vault,
            "redis": self.redis,  # Triggers lazy init if needed
            "embedder": self.embedder,  # Triggers lazy init if needed
            "tier_manager": self.tier_manager,  # Triggers lazy init if needed
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
        logger.debug("Handlers initialized")

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
        # Ensure handlers are initialized on first tool call
        self._ensure_handlers_initialized()

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
            # Validation errors are safe to show (they don't contain internal details)
            logger.warning(f"Validation error in {name}: {e}")
            return {"content": [{"type": "text", "text": f"Validation error: {str(e)}"}], "isError": True}
        except Exception as e:
            # Log full error for debugging, but sanitize message for client
            logger.error(f"Error in tool {name}: {e}", exc_info=True)
            safe_message = _sanitize_error_message(e)
            return {"content": [{"type": "text", "text": f"Error: {safe_message}"}], "isError": True}

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
