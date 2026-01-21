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
            "description": (
                "Commit important information to your persistent memory. "
                "STORE when you learn: user preferences, project decisions, resolved errors "
                "and their solutions, architectural choices, or anything the user would "
                "expect you to remember in future conversations. If you would want to know "
                "it next time, store it now."
            ),
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
            "description": (
                "Search your persistent memory for relevant context. "
                "USE THIS FIRST when: the user references past work, asks about previous "
                "conversations, mentions a project by name, or when you need context not "
                "present in the current conversation. This is your actual memory - not "
                "searching it is like ignoring what you already know about this user."
            ),
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
            "description": (
                "Recall a specific memory by its ID when you know exactly which memory "
                "you need. Use memory_search first to find IDs if you don't have them."
            ),
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
            "description": (
                "Remove a specific memory when it's outdated, incorrect, or no longer "
                "relevant. Use when user preferences change or previous decisions are "
                "superseded by new information."
            ),
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
            "description": (
                "List recent memories, optionally filtered by type or project. "
                "Use this to get an overview of what you remember about a topic or "
                "project before diving deeper with memory_search. Good for orientation "
                "at the start of a session or when returning to a project."
            ),
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
            "description": (
                "Save current session state for later restoration. "
                "SAVE when: ending a work session, switching projects, before destructive "
                "operations, or when the user indicates they will continue later. This "
                "preserves your working context across conversations."
            ),
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
            "description": (
                "Restore your working context from a previous session. "
                "CALL THIS AT CONVERSATION START when the user is continuing work on a "
                "known project or references previous work. This loads active files, recent "
                "decisions, and project state. Without it, you are starting without context."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                }
            }
        },
        {
            "name": "vault_write",
            "description": (
                "Write a note to the Obsidian-compatible vault for human-readable storage. "
                "Use for: documentation, code snippets worth preserving, conversation logs, "
                "and reference materials. These notes are accessible outside Claude and "
                "can be version-controlled or shared."
            ),
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
            "description": (
                "Read a note from the Obsidian vault. Use this to access previously "
                "saved documentation, code snippets, and reference materials that exist "
                "in human-readable form outside of memory storage."
            ),
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
            "description": (
                "Get memory system statistics and health information. Use this to "
                "understand memory utilization, storage efficiency, and system status. "
                "Useful for debugging or monitoring memory system performance."
            ),
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
