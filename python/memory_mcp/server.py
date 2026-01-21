# server.py
# Memory MCP Server for Claude Code++
# Jeremiah Kroesche | Halfservers LLC
#
# MCP protocol server exposing memory operations

import asyncio
import json
import logging
import os
import re
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


# Allowed document types
ALLOWED_DOC_TYPES = frozenset(["code", "note", "reference", "conversation"])

# Max content size: 1MB
MAX_CONTENT_SIZE = 1048576

# Tag validation pattern: alphanumeric and hyphen only
TAG_PATTERN = re.compile(r'^[a-zA-Z0-9-]+$')

# Project name validation pattern: alphanumeric, hyphen, and underscore only
PROJECT_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_string(value: Any, name: str, min_len: int = 0, max_len: int = 100000) -> str:
    """Validate and return a string value."""
    if value is None:
        raise ValueError(f"{name} is required")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {type(value).__name__}")
    if len(value) < min_len:
        raise ValueError(f"{name} must be at least {min_len} characters")
    if len(value) > max_len:
        raise ValueError(f"{name} must be at most {max_len} characters")
    return value


def validate_int(value: Any, name: str, min_val: int = None, max_val: int = None) -> int:
    """Validate and return an integer value."""
    if value is None:
        raise ValueError(f"{name} is required")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    result = int(value)
    if min_val is not None and result < min_val:
        raise ValueError(f"{name} must be at least {min_val}")
    if max_val is not None and result > max_val:
        raise ValueError(f"{name} must be at most {max_val}")
    return result


def validate_list(value: Any, name: str, item_type: type = str) -> List:
    """Validate and return a list value."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list, got {type(value).__name__}")
    for i, item in enumerate(value):
        if not isinstance(item, item_type):
            raise TypeError(f"{name}[{i}] must be {item_type.__name__}")
    return value


def validate_doc_type(value: Any, name: str = "type") -> str:
    """Validate document type against allowed values."""
    value = validate_string(value, name)
    if value not in ALLOWED_DOC_TYPES:
        raise ValueError(
            f"Invalid {name}: '{value}'. Must be one of: {', '.join(sorted(ALLOWED_DOC_TYPES))}"
        )
    return value


def validate_tags(value: Any, name: str = "tags") -> List[str]:
    """Validate and sanitize tags array (alphanumeric + hyphen only)."""
    tags = validate_list(value, name, str)
    sanitized = []
    for i, tag in enumerate(tags):
        if not tag:
            continue
        if not TAG_PATTERN.match(tag):
            raise ValueError(
                f"{name}[{i}] '{tag}' contains invalid characters. "
                "Tags must be alphanumeric with hyphens only."
            )
        sanitized.append(tag)
    return sanitized


def validate_project(value: Any, name: str = "project") -> Optional[str]:
    """Validate project name (no special characters except hyphen/underscore)."""
    if value is None:
        return None
    project = validate_string(value, name, max_len=100)
    if not PROJECT_PATTERN.match(project):
        raise ValueError(
            f"Invalid {name}: '{project}'. "
            "Project names must be alphanumeric with hyphens and underscores only."
        )
    return project


def validate_content(value: Any, name: str = "content") -> str:
    """Validate content with size limit (max 1MB)."""
    content = validate_string(value, name, min_len=1)
    content_bytes = len(content.encode('utf-8'))
    if content_bytes > MAX_CONTENT_SIZE:
        raise ValueError(
            f"{name} exceeds maximum size of {MAX_CONTENT_SIZE} bytes "
            f"(got {content_bytes} bytes)"
        )
    return content


def validate_limit(value: Any, name: str = "limit", default: int = 10) -> int:
    """Validate limit parameter (1-1000 range)."""
    if value is None:
        return default
    return validate_int(value, name, min_val=1, max_val=1000)


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
        return {
            "protocolVersion": "2024-11-05",
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
        tools = [
            {
                "name": "memory_store",
                "description": "Store content in long-term memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to store"},
                        "type": {"type": "string", "enum": ["code", "note", "conversation", "reference"]},
                        "source": {"type": "string", "description": "Source identifier (file path, URL, etc)"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "project": {"type": "string", "description": "Project name"}
                    },
                    "required": ["content", "type", "source"]
                }
            },
            {
                "name": "memory_search",
                "description": "Search memory using text or semantic similarity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "type": {"type": "string", "enum": ["text", "semantic", "hybrid"]},
                        "limit": {"type": "integer", "default": 10},
                        "filters": {
                            "type": "object",
                            "properties": {
                                "doc_type": {"type": "string"},
                                "project": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "memory_recall",
                "description": "Recall a specific memory by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Document ID"}
                    },
                    "required": ["id"]
                }
            },
            {
                "name": "memory_delete",
                "description": "Delete a memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Document ID to delete"}
                    },
                    "required": ["id"]
                }
            },
            {
                "name": "memory_list",
                "description": "List recent memories",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                        "type": {"type": "string"},
                        "project": {"type": "string"}
                    }
                }
            },
            {
                "name": "session_save",
                "description": "Save current session state",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string"},
                        "active_files": {"type": "array", "items": {"type": "string"}},
                        "context": {"type": "object"}
                    },
                    "required": ["project_path"]
                }
            },
            {
                "name": "session_restore",
                "description": "Restore a previous session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"}
                    }
                }
            },
            {
                "name": "vault_write",
                "description": "Write a note to the Obsidian vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Note path (without .md)"},
                        "content": {"type": "string"},
                        "folder": {"type": "string", "enum": ["code", "notes", "conversations", "references", "daily"]},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "vault_read",
                "description": "Read a note from the vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Note path"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "memory_stats",
                "description": "Get memory system statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

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
            except Exception:
                pass

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
        """Get system statistics."""
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
            }
        }

        # SQLite stats
        try:
            sqlite_stats = self.sqlite.get_stats()
            stats["sqlite_count"] = sqlite_stats.get("total_documents", 0)
            stats["sqlite"] = sqlite_stats
        except Exception as e:
            logger.warning(f"Failed to get SQLite stats: {e}")

        # Vault stats
        try:
            stats["vault"] = self.vault.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get vault stats: {e}")

        # Redis stats
        if self.redis:
            try:
                stats["redis"] = self.redis.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")

        # FAISS stats
        if self.faiss:
            stats["faiss"] = {
                "total_vectors": self.faiss.count,
                "dimension": self.faiss.dimension
            }

        # Embedder info
        if self.embedder:
            stats["embedder"] = {
                "provider": self.embedder.name
            }

        logger.debug(f"Stats gathered: {stats['sqlite_count']} documents in SQLite")
        return stats

    # MCP Server Loop

    async def run_stdio(self):
        """Run MCP server over stdio."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                request = json.loads(line.decode())
                response = self._handle_request(request)
                response_line = json.dumps(response) + "\n"
                writer.write(response_line.encode())
                await writer.drain()

            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_response = self._create_error(-32603, str(e), 0)
                writer.write((json.dumps(error_response) + "\n").encode())
                await writer.drain()

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
        elif method == "notifications/initialized":
            return self._create_response({}, request_id)
        else:
            return self._create_error(-32601, f"Unknown method: {method}", request_id)


def main():
    """Entry point for the MCP server."""
    server = MemoryMCPServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
