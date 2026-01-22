# server_sdk.py
# Memory MCP Server using official MCP SDK
# Jeremiah Kroesche | Halfservers LLC

import asyncio
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging to file only (not stdout/stderr which interfere with MCP)
LOG_FILE = os.environ.get("MEMORY_MCP_LOG_FILE", "/tmp/memory-mcp-sdk.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE)] if LOG_FILE else []
)
logger = logging.getLogger("memory_mcp_sdk")

# Import our existing components
from .sqlite_index import SQLiteIndex
from .vault_manager import VaultManager
from .redis_client import RedisClient, REDIS_AVAILABLE
from .faiss_manager import FAISSManager, FAISS_AVAILABLE
from .config import get_config

# Create the MCP server
server = Server("claude-code-pp-memory")

# Initialize components lazily
_index = None
_vault = None
_redis = None
_faiss = None

def get_components():
    global _index, _vault, _redis, _faiss
    if _index is None:
        config = get_config()
        _index = SQLiteIndex()
        _vault = VaultManager()
        if REDIS_AVAILABLE:
            _redis = RedisClient()
            logger.info("Redis connected")
        if FAISS_AVAILABLE:
            _faiss = FAISSManager()
            logger.info(f"FAISS initialized with {_faiss.index.ntotal} vectors")
    return _index, _vault, _redis, _faiss

# Define tools
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    logger.info("tools/list called")
    return [
        Tool(
            name="memory_store",
            description="Store content in long-term memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "type": {"type": "string", "enum": ["code", "note", "conversation", "reference"]},
                    "source": {"type": "string", "description": "Source identifier"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "project": {"type": "string", "description": "Project name"}
                },
                "required": ["content", "type", "source"]
            }
        ),
        Tool(
            name="memory_search",
            description="Search memory using text or semantic similarity",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "type": {"type": "string", "enum": ["text", "semantic", "hybrid"]},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="memory_list",
            description="List recent memories",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "type": {"type": "string"},
                    "project": {"type": "string"}
                }
            }
        ),
        Tool(
            name="memory_recall",
            description="Recall a specific memory by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Document ID"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="memory_delete",
            description="Delete a memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Document ID to delete"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="session_save",
            description="Save current session state",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "active_files": {"type": "array", "items": {"type": "string"}},
                    "context": {"type": "object"}
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="session_restore",
            description="Restore a previous session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                }
            }
        ),
        Tool(
            name="vault_write",
            description="Write a note to the Obsidian vault",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path (without .md)"},
                    "content": {"type": "string"},
                    "folder": {"type": "string", "enum": ["code", "notes", "conversations", "references", "daily"]},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="vault_read",
            description="Read a note from the vault",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="memory_stats",
            description="Get memory system statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"tools/call: {name} with {arguments}")

    index, vault, redis, faiss = get_components()

    if name == "memory_store":
        from .sqlite_index import MemoryDocument
        import uuid
        from datetime import datetime, timezone

        doc = MemoryDocument(
            id=str(uuid.uuid4()),
            content=arguments["content"],
            doc_type=arguments["type"],
            source=arguments["source"],
            tags=arguments.get("tags", []),
            project=arguments.get("project"),
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={}
        )
        index.insert(doc)
        return [TextContent(type="text", text=f"Stored memory with ID: {doc.id}")]

    elif name == "memory_search":
        results = index.search_fulltext(
            query=arguments["query"],
            limit=arguments.get("limit", 10)
        )
        if not results:
            return [TextContent(type="text", text="No results found")]

        text = f"Found {len(results)} results:\n\n"
        for doc in results:
            text += f"- [{doc.doc_type}] {doc.source}: {doc.content[:100]}...\n"
        return [TextContent(type="text", text=text)]

    elif name == "memory_list":
        results = index.get_recent(
            limit=arguments.get("limit", 20)
        )
        if not results:
            return [TextContent(type="text", text="No memories found")]

        text = f"Recent {len(results)} memories:\n\n"
        for doc in results:
            text += f"- [{doc.doc_type}] {doc.source}: {doc.content[:50]}...\n"
        return [TextContent(type="text", text=text)]

    elif name == "memory_recall":
        doc = index.get(arguments["id"])
        if not doc:
            return [TextContent(type="text", text=f"Memory not found: {arguments['id']}")]
        text = f"""Memory {doc.id}:
- Type: {doc.doc_type}
- Source: {doc.source}
- Created: {doc.created_at}
- Tags: {', '.join(doc.tags) if doc.tags else 'none'}
- Project: {doc.project or 'none'}

Content:
{doc.content}"""
        return [TextContent(type="text", text=text)]

    elif name == "memory_delete":
        success = index.delete(arguments["id"])
        if success:
            return [TextContent(type="text", text=f"Deleted memory: {arguments['id']}")]
        return [TextContent(type="text", text=f"Memory not found: {arguments['id']}")]

    elif name == "session_save":
        if not redis:
            return [TextContent(type="text", text="Session save requires Redis (not available)")]
        from .redis_client import SessionState
        import uuid
        from datetime import datetime, timezone
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        context = arguments.get("context", {})
        # Convert context dict to context_window list format
        context_window = [context] if context else []
        state = SessionState(
            session_id=session_id,
            project_path=arguments["project_path"],
            active_files=arguments.get("active_files", []),
            recent_queries=[],
            context_window=context_window,
            created_at=now,
            updated_at=now
        )
        redis.save_session(state)
        return [TextContent(type="text", text=f"Session saved with ID: {session_id}")]

    elif name == "session_restore":
        if not redis:
            return [TextContent(type="text", text="Session restore requires Redis (not available)")]
        session_id = arguments.get("session_id")
        if session_id:
            state = redis.get_session(session_id)
        else:
            # Note: Latest session retrieval not yet implemented
            # For now, return empty state if no session_id provided
            state = None
        if not state:
            return [TextContent(type="text", text="No session found")]
        text = f"""Restored session {state.session_id}:
- Project: {state.project_path}
- Active files: {', '.join(state.active_files) if state.active_files else 'none'}
- Context keys: {list(state.context.keys()) if state.context else 'none'}"""
        return [TextContent(type="text", text=text)]

    elif name == "vault_write":
        note = vault.write_note(
            path=arguments["path"],
            content=arguments["content"],
            folder=arguments.get("folder"),
            frontmatter={"tags": arguments.get("tags", [])}
        )
        return [TextContent(type="text", text=f"Written to vault: {note.path}")]

    elif name == "vault_read":
        note = vault.read_note(arguments["path"])
        if not note:
            return [TextContent(type="text", text=f"Note not found: {arguments['path']}")]
        text = f"""Note: {note.title}
Path: {note.path}
Tags: {', '.join(note.tags) if note.tags else 'none'}
Created: {note.created_at}
Modified: {note.modified_at}

{note.content}"""
        return [TextContent(type="text", text=text)]

    elif name == "memory_stats":
        stats = index.get_stats()
        vault_stats = vault.get_stats()

        text = f"""Memory Statistics:
- Total documents: {stats.get('total_documents', 0)}
- By type: {stats.get('by_type', {})}
- Vault notes: {vault_stats.get('total_notes', 0)}
- FAISS vectors: {faiss.index.ntotal if faiss else 'N/A'}
- Redis: {'available' if redis else 'N/A'}"""
        return [TextContent(type="text", text=text)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Run the MCP server."""
    logger.info("Starting Memory MCP Server (SDK version)")

    # Initialize components early
    get_components()

    async with stdio_server() as (read_stream, write_stream):
        logger.info("stdio server started")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

def run():
    """Entry point."""
    asyncio.run(main())

if __name__ == "__main__":
    run()
