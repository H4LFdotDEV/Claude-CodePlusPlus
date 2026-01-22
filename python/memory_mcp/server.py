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
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import numpy as np

from .config import get_config, MemoryConfig, set_config
from .sqlite_index import SQLiteIndex, MemoryDocument
from .vault_manager import VaultManager
from .redis_client import RedisClient, SessionState, REDIS_AVAILABLE
from .faiss_manager import FAISSManager, FAISS_AVAILABLE
from .embedding_provider import get_embedding_provider, FallbackEmbeddingProvider
from .validation import (
    validate_string, validate_int, validate_list, validate_doc_type,
    validate_tags, validate_project, validate_content, validate_limit,
    ALLOWED_DOC_TYPES, MAX_CONTENT_SIZE
)
from .tool_schemas import get_tool_schemas

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

        # Initialize components
        self.sqlite = SQLiteIndex()
        self.vault = VaultManager()

        # Optional components (may not be available)
        self.redis: Optional[RedisClient] = None
        self.faiss: Optional[FAISSManager] = None
        self.embedder: Optional[FallbackEmbeddingProvider] = None

        self._init_optional_components()

        # MCP state
        self._request_id = 0
        self._session_id = str(uuid.uuid4())

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

        # FAISS (vector search)
        if FAISS_AVAILABLE:
            try:
                self.faiss = FAISSManager()
                logger.info(f"FAISS initialized with {self.faiss.count} vectors")
            except Exception as e:
                logger.warning(f"FAISS initialization failed: {e}")
                self.faiss = None
        else:
            logger.info("FAISS not available - install with: pip install faiss-cpu")

        # Embeddings
        try:
            self.embedder = get_embedding_provider()
            logger.info(f"Embedding provider: {self.embedder.name}")
        except Exception as e:
            logger.warning(f"Embedding provider initialization failed: {e}")
            self.embedder = None

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text with Redis caching for performance."""
        # Check cache first
        if self.redis:
            try:
                cached = self.redis.get_cached_embedding(text)
                if cached is not None:
                    logger.debug("Embedding cache hit")
                    return np.array(cached, dtype=np.float32)
            except Exception as e:
                logger.debug(f"Redis embedding cache lookup failed: {e}")

        # Generate embedding
        embedding = self.embedder.embed(text)

        # Cache for next time (24 hour TTL)
        if self.redis:
            try:
                self.redis.cache_embedding(text, embedding.tolist(), ttl=86400)
                logger.debug("Cached embedding in Redis")
            except Exception as e:
                logger.debug(f"Redis embedding cache store failed: {e}")

        return embedding

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
        """Handle tool invocation."""
        handlers = {
            "memory_store": self._tool_memory_store,
            "memory_search": self._tool_memory_search,
            "memory_recall": self._tool_memory_recall,
            "memory_delete": self._tool_memory_delete,
            "memory_list": self._tool_memory_list,
            "session_save": self._tool_session_save,
            "session_restore": self._tool_session_restore,
            "vault_write": self._tool_vault_write,
            "vault_read": self._tool_vault_read,
            "memory_stats": self._tool_memory_stats
        }

        handler = handlers.get(name)
        if not handler:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        try:
            logger.debug(f"Calling tool: {name} with args: {list(arguments.keys())}")
            result = handler(arguments)
            logger.debug(f"Tool {name} completed successfully")
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        except (ValueError, TypeError) as e:
            logger.warning(f"Validation error in {name}: {e}")
            return {"content": [{"type": "text", "text": f"Validation error: {str(e)}"}], "isError": True}
        except Exception as e:
            logger.error(f"Error in tool {name}: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}

    # Tool Implementations

    def _tool_memory_store(self, args: Dict) -> Dict:
        """Store content in memory."""
        # Validate required fields with comprehensive validation
        content = validate_content(args.get("content"), "content")
        doc_type = validate_doc_type(args.get("type"), "type")
        source = validate_string(args.get("source"), "source", min_len=1, max_len=1000)
        tags = validate_tags(args.get("tags"), "tags")
        project = validate_project(args.get("project"), "project")

        doc_id = str(uuid.uuid4())[:16]

        # Create document
        doc = MemoryDocument(
            id=doc_id,
            content=content,
            doc_type=doc_type,
            source=source,
            project=project,
            tags=tags
        )

        # Generate embedding if available
        if self.embedder and self.faiss:
            try:
                embedding = self.embedder.embed(content)
                self.faiss.add(doc_id, embedding)
                doc.embedding_id = doc_id
                self.faiss.save()
                logger.debug(f"Generated embedding for doc {doc_id}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
                # Continue without embedding

        # Store in SQLite
        self.sqlite.insert(doc)
        logger.info(f"Stored document {doc_id} of type {doc_type}")

        # Also write to vault for human access
        if doc_type == "code":
            self.vault.write_code_note(
                source,
                content,
                args.get("language", "text"),
                tags=tags
            )
        elif doc_type == "note":
            self.vault.write_note(
                f"notes/{doc_id}",
                content,
                {"type": "note", "source": source, "tags": tags}
            )

        # Cache in Redis if available
        if self.redis:
            try:
                self.redis.cache_query(content[:100], doc_id)
            except Exception as e:
                logger.debug(f"Redis cache failed: {e}")

        return {"id": doc_id, "stored": True}

    def _tool_memory_search(self, args: Dict) -> Dict:
        """Search memories."""
        query = validate_string(args.get("query"), "query", min_len=1, max_len=10000)
        search_type = args.get("type", "hybrid")
        limit = validate_limit(args.get("limit"), "limit", default=10)
        # Clamp to reasonable search limit
        limit = min(limit, 100)
        filters = args.get("filters", {}) or {}

        if search_type not in ["text", "semantic", "hybrid"]:
            raise ValueError(f"Invalid search type: {search_type}. Must be one of: text, semantic, hybrid")

        logger.debug(f"Searching for: '{query[:50]}...' type={search_type} limit={limit}")

        results = []
        seen_ids: set = set()  # O(1) deduplication lookup

        # Text search via SQLite FTS
        if search_type in ["text", "hybrid"]:
            text_results = self.sqlite.search_fulltext(query, limit=limit * 2)
            for doc in text_results:
                if self._matches_filters(doc, filters):
                    if doc.id not in seen_ids:
                        seen_ids.add(doc.id)
                        results.append({
                            "id": doc.id,
                            "content": doc.content[:500],
                            "type": doc.doc_type,
                            "source": doc.source,
                            "score": 1.0,
                            "match_type": "text"
                        })

        # Semantic search via FAISS
        if search_type in ["semantic", "hybrid"] and self.embedder and self.faiss:
            try:
                query_embedding = self._get_embedding(query)
                faiss_results = self.faiss.search(query_embedding, k=limit)

                doc_ids = [r.doc_id for r in faiss_results]
                docs = self.sqlite.get_by_embedding_ids(doc_ids)
                doc_map = {d.id: d for d in docs}

                for fr in faiss_results:
                    if fr.doc_id in doc_map:
                        doc = doc_map[fr.doc_id]
                        if self._matches_filters(doc, filters):
                            # Avoid duplicates in hybrid mode using O(1) set lookup
                            if doc.id not in seen_ids:
                                seen_ids.add(doc.id)
                                results.append({
                                    "id": doc.id,
                                    "content": doc.content[:500],
                                    "type": doc.doc_type,
                                    "source": doc.source,
                                    "score": fr.score,
                                    "match_type": "semantic"
                                })
            except Exception as e:
                logger.debug(f"Semantic search failed (falling back to text): {e}")

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:limit], "total": len(results)}

    def _matches_filters(self, doc: MemoryDocument, filters: Dict) -> bool:
        """Check if document matches filters."""
        if not filters:
            return True
        if filters.get("doc_type") and doc.doc_type != filters["doc_type"]:
            return False
        if filters.get("project") and doc.project != filters["project"]:
            return False
        if filters.get("tags"):
            if not any(t in doc.tags for t in filters["tags"]):
                return False
        return True

    def _tool_memory_recall(self, args: Dict) -> Dict:
        """Recall specific memory."""
        doc_id = validate_string(args.get("id"), "id", min_len=1, max_len=64)
        logger.debug(f"Recalling document: {doc_id}")

        doc = self.sqlite.get(doc_id)
        if not doc:
            logger.debug(f"Document not found: {doc_id}")
            return {"found": False, "id": doc_id}

        logger.debug(f"Found document: {doc_id}")
        return {
            "found": True,
            "document": {
                "id": doc.id,
                "content": doc.content,
                "type": doc.doc_type,
                "source": doc.source,
                "project": doc.project,
                "tags": doc.tags,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at
            }
        }

    def _tool_memory_delete(self, args: Dict) -> Dict:
        """Delete a memory."""
        doc_id = validate_string(args.get("id"), "id", min_len=1, max_len=64)
        logger.debug(f"Deleting document: {doc_id}")

        # Delete from FAISS
        if self.faiss:
            try:
                self.faiss.delete(doc_id)
                self.faiss.save()
                logger.debug(f"Deleted from FAISS: {doc_id}")
            except Exception as e:
                logger.warning(f"FAISS deletion failed for {doc_id}: {e}")

        # Delete from SQLite
        deleted = self.sqlite.delete(doc_id)
        if deleted:
            logger.info(f"Deleted document: {doc_id}")
        else:
            logger.debug(f"Document not found for deletion: {doc_id}")

        return {"deleted": deleted, "id": doc_id}

    def _tool_memory_list(self, args: Dict) -> Dict:
        """List recent memories."""
        limit = validate_limit(args.get("limit"), "limit", default=20)
        # Clamp to reasonable list limit
        limit = min(limit, 100)

        doc_type = args.get("type")
        project = args.get("project")

        # Validate doc_type if provided
        if doc_type:
            doc_type = validate_doc_type(doc_type, "type")

        # Validate project if provided
        if project:
            project = validate_project(project, "project")

        logger.debug(f"Listing memories: type={doc_type} project={project} limit={limit}")

        if doc_type:
            docs = self.sqlite.search_by_type(doc_type, limit)
        elif project:
            docs = self.sqlite.search_by_project(project, limit)
        else:
            docs = self.sqlite.get_recent(limit)

        logger.debug(f"Found {len(docs)} memories")

        return {
            "documents": [{
                "id": d.id,
                "type": d.doc_type,
                "source": d.source,
                "preview": d.content[:200],
                "updated_at": d.updated_at
            } for d in docs],
            "count": len(docs)
        }

    def _tool_session_save(self, args: Dict) -> Dict:
        """Save session state."""
        project_path = validate_string(args.get("project_path"), "project_path", min_len=1)
        active_files = validate_list(args.get("active_files"), "active_files", str)
        context = args.get("context", {}) or {}

        logger.debug(f"Saving session for project: {project_path}")

        if not self.redis:
            # Fallback: Store in SQLite as a note
            logger.info("Redis not available - saving session to SQLite")
            doc = MemoryDocument(
                id=self._session_id,
                content=json.dumps({
                    "project_path": project_path,
                    "active_files": active_files,
                    "context": context
                }),
                doc_type="session",
                source=f"session:{project_path}",
                project=project_path
            )
            self.sqlite.insert(doc)
            return {"session_id": self._session_id, "saved": True, "backend": "sqlite"}

        session = SessionState(
            session_id=self._session_id,
            project_path=project_path,
            active_files=active_files,
            recent_queries=[],
            context_window=context.get("messages", []),
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )

        self.redis.save_session(session)
        logger.info(f"Session saved: {self._session_id}")
        return {"session_id": self._session_id, "saved": True, "backend": "redis"}

    def _tool_session_restore(self, args: Dict) -> Dict:
        """Restore session."""
        session_id = args.get("session_id")

        if not self.redis:
            # Fallback: Try to restore from SQLite
            logger.info("Redis not available - restoring session from SQLite")
            if not session_id:
                # List sessions from SQLite
                docs = self.sqlite.search_by_type("session", limit=20)
                return {
                    "available_sessions": [{"id": d.id, "project": d.project} for d in docs],
                    "backend": "sqlite"
                }

            doc = self.sqlite.get(session_id)
            if not doc:
                return {"found": False, "session_id": session_id}

            try:
                session_data = json.loads(doc.content)
                self._session_id = session_id
                return {
                    "found": True,
                    "session_id": session_id,
                    "project_path": session_data.get("project_path"),
                    "active_files": session_data.get("active_files", []),
                    "restored": True,
                    "backend": "sqlite"
                }
            except json.JSONDecodeError:
                return {"found": False, "error": "Invalid session data"}

        logger.debug(f"Restoring session: {session_id or 'listing all'}")

        if not session_id:
            # List available sessions
            sessions = self.redis.list_sessions()
            return {"available_sessions": sessions, "backend": "redis"}

        session = self.redis.get_session(session_id)
        if not session:
            logger.debug(f"Session not found: {session_id}")
            return {"found": False, "session_id": session_id}

        self._session_id = session_id
        logger.info(f"Session restored: {session_id}")
        return {
            "found": True,
            "session_id": session.session_id,
            "project_path": session.project_path,
            "active_files": session.active_files,
            "restored": True,
            "backend": "redis"
        }

    def _tool_vault_write(self, args: Dict) -> Dict:
        """Write to vault."""
        path = validate_string(args.get("path"), "path", min_len=1, max_len=500)
        content = validate_string(args.get("content"), "content", min_len=0)
        tags = validate_list(args.get("tags"), "tags", str)
        folder = args.get("folder", "notes")

        valid_folders = ["code", "notes", "conversations", "references", "daily"]
        if folder not in valid_folders:
            raise ValueError(f"Invalid folder: {folder}. Must be one of: {', '.join(valid_folders)}")

        logger.debug(f"Writing to vault: {folder}/{path}")

        frontmatter = {"tags": tags}

        note = self.vault.write_note(
            path,
            content,
            frontmatter,
            folder=folder
        )

        logger.info(f"Vault note written: {note.path}")
        return {"path": note.path, "written": True}

    def _tool_vault_read(self, args: Dict) -> Dict:
        """Read from vault."""
        path = validate_string(args.get("path"), "path", min_len=1, max_len=500)
        logger.debug(f"Reading from vault: {path}")

        note = self.vault.read_note(path)
        if not note:
            logger.debug(f"Vault note not found: {path}")
            return {"found": False, "path": path}

        logger.debug(f"Vault note found: {path}")
        return {
            "found": True,
            "path": note.path,
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "links": note.links,
            "modified_at": note.modified_at
        }

    def _tool_memory_stats(self, args: Dict) -> Dict:
        """Get system statistics with health checks.

        Returns comprehensive stats including:
        - sqlite_count: Total documents in cold storage
        - session_id: Current server session ID
        - components: Boolean availability of each component
        - health: Status and latency for each component
        - Detailed stats for sqlite, vault, redis, faiss, embedder
        """
        import time
        logger.debug("Gathering memory statistics")

        stats = {
            "sqlite_count": 0,
            "session_id": self._session_id,
            "components": {
                "sqlite": True,
                "vault": True,
                "redis": self.redis is not None,
                "faiss": self.faiss is not None,
                "embedder": self.embedder is not None
            },
            "health": {}
        }

        # SQLite stats with health check
        try:
            start = time.time()
            sqlite_stats = self.sqlite.get_stats()
            latency_ms = (time.time() - start) * 1000
            stats["sqlite_count"] = sqlite_stats.get("total_documents", 0)
            stats["sqlite"] = sqlite_stats
            stats["health"]["sqlite"] = {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get SQLite stats: {e}")
            stats["health"]["sqlite"] = {"status": "error", "error": str(e)}

        # Vault stats with health check
        try:
            start = time.time()
            vault_stats = self.vault.get_stats()
            latency_ms = (time.time() - start) * 1000
            stats["vault"] = vault_stats
            stats["health"]["vault"] = {
                "status": "connected",
                "latency_ms": round(latency_ms, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get vault stats: {e}")
            stats["health"]["vault"] = {"status": "error", "error": str(e)}

        # Redis stats with health check
        if self.redis:
            try:
                start = time.time()
                redis_stats = self.redis.get_stats()
                health_ok = self.redis.health_check()
                latency_ms = (time.time() - start) * 1000
                stats["redis"] = redis_stats
                stats["health"]["redis"] = {
                    "status": "healthy" if health_ok else "degraded",
                    "latency_ms": round(latency_ms, 2)
                }
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
                stats["health"]["redis"] = {"status": "error", "error": str(e)}
        else:
            stats["health"]["redis"] = {"status": "not_available"}

        # FAISS stats with health check
        if self.faiss:
            try:
                start = time.time()
                faiss_stats = {
                    "total_vectors": self.faiss.count,
                    "dimension": self.faiss.dimension,
                    "index_type": self.faiss.config.index_type if hasattr(self.faiss, 'config') else "unknown",
                    "deleted_count": getattr(self.faiss, 'deleted_count', 0),
                    "total_added": getattr(self.faiss, 'total_added', self.faiss.count)
                }
                latency_ms = (time.time() - start) * 1000
                stats["faiss"] = faiss_stats
                stats["health"]["faiss"] = {
                    "status": "available",
                    "latency_ms": round(latency_ms, 2)
                }
            except Exception as e:
                logger.warning(f"Failed to get FAISS stats: {e}")
                stats["health"]["faiss"] = {"status": "error", "error": str(e)}
        else:
            stats["health"]["faiss"] = {"status": "not_available"}

        # Embedder info with health check
        if self.embedder:
            try:
                stats["embedder"] = {
                    "provider": self.embedder.name,
                    "dimension": getattr(self.embedder, 'dimension', None)
                }
                stats["health"]["embedder"] = {"status": "active"}
            except Exception as e:
                logger.warning(f"Failed to get embedder info: {e}")
                stats["health"]["embedder"] = {"status": "error", "error": str(e)}
        else:
            stats["health"]["embedder"] = {"status": "not_available"}

        logger.debug(f"Stats gathered: {stats['sqlite_count']} documents in SQLite")
        return stats

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
