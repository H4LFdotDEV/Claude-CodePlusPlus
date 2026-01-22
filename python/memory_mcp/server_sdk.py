# server_sdk.py
# Memory MCP Server using official MCP SDK
# Jeremiah Kroesche | Halfservers LLC

import asyncio
import logging
import os
import sys
import threading
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

# Import new tier components
try:
    from .graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE
except ImportError:
    GRAPHITI_AVAILABLE = False
    GraphitiManager = None

try:
    from .livegrep_client import LivegrepClient, HTTPX_AVAILABLE as LIVEGREP_AVAILABLE
except ImportError:
    LIVEGREP_AVAILABLE = False
    LivegrepClient = None

# Create the MCP server
server = Server("claude-code-pp-memory")

# Initialize components lazily with thread-safe double-checked locking
_index = None
_vault = None
_redis = None
_faiss = None
_graphiti = None
_livegrep = None
_components_lock = threading.Lock()


def get_components():
    """Get memory components with thread-safe lazy initialization.

    Returns tuple of:
        - index: SQLiteIndex (metadata storage)
        - vault: VaultManager (human-readable archive)
        - redis: RedisClient (hot session cache)
        - faiss: FAISSManager (legacy vector search - deprecated)
        - graphiti: GraphitiManager (warm knowledge graph)
        - livegrep: LivegrepClient (cold code search)
    """
    global _index, _vault, _redis, _faiss, _graphiti, _livegrep
    # First check without lock (fast path)
    if _index is None:
        with _components_lock:
            # Second check with lock (thread-safe initialization)
            if _index is None:
                config = get_config()

                # Tier: Metadata storage (SQLite)
                _index = SQLiteIndex()

                # Tier 4: Archive (Obsidian Vault)
                _vault = VaultManager()

                # Tier 1: Hot (Redis)
                if REDIS_AVAILABLE:
                    _redis = RedisClient()
                    logger.info("Redis connected (hot tier)")

                # Tier 2: Warm - Legacy FAISS (deprecated, use Graphiti)
                if FAISS_AVAILABLE:
                    _faiss = FAISSManager()
                    logger.info(f"FAISS initialized with {_faiss.index.ntotal} vectors (legacy)")

                # Tier 2: Warm - Graphiti Knowledge Graph
                if GRAPHITI_AVAILABLE and config.graphiti.enabled:
                    _graphiti = GraphitiManager(
                        uri=config.graphiti.uri,
                        user=config.graphiti.user,
                        password=config.graphiti.password,
                        openai_api_key=config.graphiti.openai_api_key
                    )
                    logger.info(f"Graphiti initialized (warm tier): {config.graphiti.uri}")

                # Tier 3: Cold - livegrep Code Search
                if LIVEGREP_AVAILABLE and config.livegrep.enabled:
                    _livegrep = LivegrepClient(endpoint=config.livegrep.endpoint)
                    if _livegrep.health_check():
                        logger.info(f"livegrep connected (cold tier): {config.livegrep.endpoint}")
                    else:
                        logger.warning("livegrep not available - code search disabled")
                        _livegrep = None

    return _index, _vault, _redis, _faiss, _graphiti, _livegrep

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
        ),
        Tool(
            name="search_entities",
            description="Search knowledge graph for entities (people, concepts, tools, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for entities"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_facts",
            description="Search knowledge graph for facts/relationships between entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for facts"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="code_search",
            description="Search code across repositories using regex patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "RE2 regex pattern to search for"},
                    "path_filter": {"type": "string", "description": "Filter by file path (e.g., '*.py')"},
                    "repo_filter": {"type": "string", "description": "Filter by repository name"},
                    "max_matches": {"type": "integer", "default": 50}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_function",
            description="Search for function/method definitions in code",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of function to find"},
                    "language": {"type": "string", "description": "Programming language (python, javascript, go, etc.)"},
                    "max_matches": {"type": "integer", "default": 20}
                },
                "required": ["function_name"]
            }
        ),
        Tool(
            name="search_class",
            description="Search for class/struct/interface definitions in code",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Name of class to find"},
                    "language": {"type": "string", "description": "Programming language"},
                    "max_matches": {"type": "integer", "default": 20}
                },
                "required": ["class_name"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"tools/call: {name} with {arguments}")

    index, vault, redis, faiss, graphiti, livegrep = get_components()

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
            preview = doc.content[:100] + "..." if len(doc.content) > 100 else doc.content
            text += f"- [{doc.doc_type}] {doc.source}: {preview}\n"
        return [TextContent(type="text", text=text)]

    elif name == "memory_list":
        results = index.get_recent(
            limit=arguments.get("limit", 20)
        )
        if not results:
            return [TextContent(type="text", text="No memories found")]

        text = f"Recent {len(results)} memories:\n\n"
        for doc in results:
            preview = doc.content[:50] + "..." if len(doc.content) > 50 else doc.content
            text += f"- [{doc.doc_type}] {doc.source}: {preview}\n"
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

        # Get Graphiti stats if available
        graphiti_status = "N/A"
        if graphiti:
            graphiti_stats = await graphiti.get_stats()
            if graphiti_stats.get("available"):
                graphiti_status = f"connected ({graphiti_stats.get('uri', 'unknown')})"
            else:
                graphiti_status = f"error: {graphiti_stats.get('error', 'unknown')}"

        # Get livegrep stats if available
        livegrep_status = "N/A"
        if livegrep:
            lg_stats = livegrep.get_stats()
            if lg_stats.get("available"):
                livegrep_status = f"connected ({lg_stats.get('endpoint', 'unknown')})"
            else:
                livegrep_status = f"unavailable"

        text = f"""Memory Statistics:

Tier Overview:
- Hot (Redis): {'available' if redis else 'N/A'}
- Warm (Graphiti): {graphiti_status}
- Warm (FAISS - legacy): {faiss.index.ntotal if faiss else 'N/A'} vectors
- Cold (livegrep): {livegrep_status}
- Archive (Vault): {vault_stats.get('total_notes', 0)} notes

Document Storage:
- Total documents: {stats.get('total_documents', 0)}
- By type: {stats.get('by_type', {})}
- Vault notes: {vault_stats.get('total_notes', 0)}"""
        return [TextContent(type="text", text=text)]

    elif name == "search_entities":
        if not graphiti:
            return [TextContent(type="text", text="Knowledge graph (Graphiti) not available")]

        entities = await graphiti.search_entities(
            query=arguments["query"],
            limit=arguments.get("limit", 10)
        )

        if not entities:
            return [TextContent(type="text", text="No entities found")]

        text = f"Found {len(entities)} entities:\n\n"
        for entity in entities:
            summary = entity.summary[:100] + "..." if len(entity.summary) > 100 else entity.summary
            text += f"- **{entity.name}**: {summary}\n"
            if entity.labels:
                text += f"  Labels: {', '.join(entity.labels)}\n"
        return [TextContent(type="text", text=text)]

    elif name == "search_facts":
        if not graphiti:
            return [TextContent(type="text", text="Knowledge graph (Graphiti) not available")]

        facts = await graphiti.search_facts(
            query=arguments["query"],
            limit=arguments.get("limit", 10)
        )

        if not facts:
            return [TextContent(type="text", text="No facts found")]

        text = f"Found {len(facts)} facts:\n\n"
        for fact in facts:
            text += f"- {fact.source_entity} → {fact.target_entity}: {fact.fact}\n"
            if fact.valid_at:
                text += f"  Valid at: {fact.valid_at}\n"
        return [TextContent(type="text", text=text)]

    elif name == "code_search":
        if not livegrep:
            return [TextContent(type="text", text="Code search (livegrep) not available")]

        response = livegrep.search(
            query=arguments["query"],
            path_filter=arguments.get("path_filter"),
            repo_filter=arguments.get("repo_filter"),
            max_matches=arguments.get("max_matches", 50)
        )

        if not response.results:
            return [TextContent(type="text", text=f"No code matches found for: {arguments['query']}")]

        text = f"Found {len(response.results)} matches ({response.duration_ms:.1f}ms):\n\n"
        for result in response.results[:20]:  # Limit output
            text += f"**{result.repo}/{result.path}:{result.line_number}**\n"
            text += f"```\n{result.line_content}\n```\n\n"

        if response.truncated:
            text += f"\n(Results truncated, {response.total_matches} total matches)"
        return [TextContent(type="text", text=text)]

    elif name == "search_function":
        if not livegrep:
            return [TextContent(type="text", text="Code search (livegrep) not available")]

        response = livegrep.search_function(
            function_name=arguments["function_name"],
            language=arguments.get("language"),
            max_matches=arguments.get("max_matches", 20)
        )

        if not response.results:
            return [TextContent(type="text", text=f"No function '{arguments['function_name']}' found")]

        text = f"Found {len(response.results)} function definitions:\n\n"
        for result in response.results:
            text += f"- **{result.repo}/{result.path}:{result.line_number}**\n"
            text += f"  `{result.line_content.strip()}`\n"
        return [TextContent(type="text", text=text)]

    elif name == "search_class":
        if not livegrep:
            return [TextContent(type="text", text="Code search (livegrep) not available")]

        response = livegrep.search_class(
            class_name=arguments["class_name"],
            language=arguments.get("language"),
            max_matches=arguments.get("max_matches", 20)
        )

        if not response.results:
            return [TextContent(type="text", text=f"No class '{arguments['class_name']}' found")]

        text = f"Found {len(response.results)} class definitions:\n\n"
        for result in response.results:
            text += f"- **{result.repo}/{result.path}:{result.line_number}**\n"
            text += f"  `{result.line_content.strip()}`\n"
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
