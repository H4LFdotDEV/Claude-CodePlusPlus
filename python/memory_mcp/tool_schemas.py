# tool_schemas.py
# MCP Tool Schema Definitions for Memory MCP Server
# Centralized schema definitions for all 10 MCP tools

from typing import List, Dict, Any


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Get the complete list of MCP tool schemas.

    Returns:
        List of tool schema dictionaries containing name, description, and inputSchema

    The returned schemas define:
    - memory_store: Store content in memory with type, tags, project
    - memory_search: Search memory by text or semantic similarity
    - memory_recall: Retrieve specific memory by ID
    - memory_delete: Delete a memory by ID
    - memory_list: List recent memories with optional filters
    - session_save: Save current session state
    - session_restore: Restore a previous session
    - vault_write: Write note to Obsidian vault
    - vault_read: Read note from Obsidian vault
    - memory_stats: Get memory system statistics
    """
    return [
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


# Tool name constants for easy reference
TOOL_MEMORY_STORE = "memory_store"
TOOL_MEMORY_SEARCH = "memory_search"
TOOL_MEMORY_RECALL = "memory_recall"
TOOL_MEMORY_DELETE = "memory_delete"
TOOL_MEMORY_LIST = "memory_list"
TOOL_SESSION_SAVE = "session_save"
TOOL_SESSION_RESTORE = "session_restore"
TOOL_VAULT_WRITE = "vault_write"
TOOL_VAULT_READ = "vault_read"
TOOL_MEMORY_STATS = "memory_stats"

# All tool names for iteration
ALL_TOOL_NAMES = [
    TOOL_MEMORY_STORE,
    TOOL_MEMORY_SEARCH,
    TOOL_MEMORY_RECALL,
    TOOL_MEMORY_DELETE,
    TOOL_MEMORY_LIST,
    TOOL_SESSION_SAVE,
    TOOL_SESSION_RESTORE,
    TOOL_VAULT_WRITE,
    TOOL_VAULT_READ,
    TOOL_MEMORY_STATS
]
