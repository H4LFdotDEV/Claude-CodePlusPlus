# tool_schemas.py
# MCP Tool Schema Definitions for Memory MCP Server
# Centralized schema definitions for all 20 MCP tools
# - 10 Core tools (memory CRUD, sessions, vault)
# - 5 Research tools (voice/whiteboard sessions)
# - 5 Tier-specific tools (knowledge graph, code search)

from typing import List, Dict, Any


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Get the complete list of MCP tool schemas.

    Returns:
        List of tool schema dictionaries containing name, description, and inputSchema

    The returned schemas define:

    Core Tools (10):
    - memory_store: Store content in memory with type, tags, project
    - memory_search: Multi-tier search by text or semantic similarity
    - memory_recall: Retrieve specific memory by ID (tracks access for promotion)
    - memory_delete: Delete a memory by ID
    - memory_list: List recent memories with optional filters
    - session_save: Save current session state
    - session_restore: Restore a previous session
    - vault_write: Write note to Obsidian vault
    - vault_read: Read note from Obsidian vault
    - memory_stats: Get memory system statistics with tier health

    Research Tools (5):
    - research_session_start: Start voice/whiteboard research session
    - research_session_end: End session with summary and action items
    - research_transcript_store: Store voice transcript segments
    - research_capture_store: Store whiteboard/webcam captures
    - research_search: Search across research data

    Tier-Specific Tools (5):
    - search_entities: Search Graphiti knowledge graph for entities
    - search_facts: Search Graphiti for facts/relationships
    - code_search: RE2 regex code search via livegrep
    - search_function: Find function definitions
    - search_class: Find class/struct definitions
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
        },
        # Research tools for voice + whiteboard sessions
        {
            "name": "research_session_start",
            "description": (
                "Start a new research session for voice conversation and whiteboard capture. "
                "BEGIN A SESSION when: starting a brainstorming session, beginning research work, "
                "or when the user wants to document an extended exploration. Sessions track "
                "transcripts, captures, and insights together."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Session name (e.g., 'Pocket Dimension Physics')"},
                    "focus_area": {"type": "string", "description": "Research focus or topic"},
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of participants (e.g., ['Jeremiah', 'Claude'])"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "research_session_end",
            "description": (
                "End a research session and generate summary. "
                "CLOSE A SESSION when: research work is complete, switching to different work, "
                "or at the end of a voice conversation. Generates a summary, writes to vault, "
                "and archives all session data."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID to end"},
                    "summary": {"type": "string", "description": "Session summary"},
                    "action_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of action items from the session"
                    },
                    "key_decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key decisions made during the session"
                    }
                },
                "required": ["session_id"]
            }
        },
        {
            "name": "research_transcript_store",
            "description": (
                "Store a voice transcript segment from a research session. "
                "STORE TRANSCRIPTS as they come in during voice conversations. Captures speaker "
                "attribution and timestamps for later review and search."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Transcript text"},
                    "speaker": {"type": "string", "description": "Speaker name (default: 'user')"},
                    "session_id": {"type": "string", "description": "Associated research session"},
                    "timestamp": {"type": "string", "description": "ISO timestamp of the segment"}
                },
                "required": ["text"]
            }
        },
        {
            "name": "research_capture_store",
            "description": (
                "Store a whiteboard or webcam capture from a research session. "
                "CAPTURE when: the user says 'capture the whiteboard', shows important "
                "diagrams, or shares visual information. Stores description, OCR text, "
                "and image path for later retrieval."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Description of what was captured"},
                    "ocr_text": {"type": "string", "description": "Extracted text from the image"},
                    "image_path": {"type": "string", "description": "Path to the image file"},
                    "session_id": {"type": "string", "description": "Associated research session"},
                    "capture_type": {
                        "type": "string",
                        "enum": ["whiteboard", "webcam", "screenshot"],
                        "description": "Type of capture (default: 'whiteboard')"
                    }
                },
                "required": ["description"]
            }
        },
        {
            "name": "research_search",
            "description": (
                "Search across research data including transcripts, captures, and sessions. "
                "USE THIS to find: past discussions, whiteboard captures, session summaries, "
                "or any research content. Supports filtering by session and type."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "session_id": {"type": "string", "description": "Filter to specific session"},
                    "type": {
                        "type": "string",
                        "enum": ["transcript", "research_image", "research_session"],
                        "description": "Filter by content type"
                    },
                    "limit": {"type": "integer", "default": 20}
                },
                "required": ["query"]
            }
        },
        # Tier-specific tools (knowledge graph and code search)
        {
            "name": "search_entities",
            "description": (
                "Search the knowledge graph for entities (people, concepts, projects, etc). "
                "Use this when you need to understand relationships between concepts or "
                "find entities mentioned across multiple conversations. Returns entity names, "
                "summaries, and labels from the Graphiti knowledge graph."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10, "description": "Max results (max 100)"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_facts",
            "description": (
                "Search the knowledge graph for facts and relationships between entities. "
                "Use this to find how concepts relate to each other or to trace decision "
                "history. Returns source entity, target entity, and the fact connecting them."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10, "description": "Max results (max 100)"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "code_search",
            "description": (
                "Search code across all indexed repositories using regex patterns. "
                "Fast (<100ms) even for large codebases. Use RE2 regex syntax. "
                "Supports path and repo filters for narrowing results."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "RE2 regex pattern to search for"},
                    "path_filter": {"type": "string", "description": "Glob pattern to filter files (e.g., '*.py')"},
                    "repo_filter": {"type": "string", "description": "Repository name to search within"},
                    "limit": {"type": "integer", "default": 50, "description": "Max results (max 200)"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_function",
            "description": (
                "Find function or method definitions by name across codebases. "
                "Searches for def/function/func patterns based on the specified language. "
                "Useful for finding where a function is defined before examining its implementation."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Function name to search for"},
                    "language": {
                        "type": "string",
                        "description": "Programming language (python, javascript, typescript, go, rust, java, c, cpp)"
                    },
                    "limit": {"type": "integer", "default": 50, "description": "Max results (max 200)"}
                },
                "required": ["name"]
            }
        },
        {
            "name": "search_class",
            "description": (
                "Find class, struct, or interface definitions by name across codebases. "
                "Searches for class/struct/interface/type patterns based on the specified language. "
                "Useful for finding type definitions and understanding code architecture."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Class/struct name to search for"},
                    "language": {
                        "type": "string",
                        "description": "Programming language (python, javascript, typescript, go, rust, java)"
                    },
                    "limit": {"type": "integer", "default": 50, "description": "Max results (max 200)"}
                },
                "required": ["name"]
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

# Research tool name constants
TOOL_RESEARCH_SESSION_START = "research_session_start"
TOOL_RESEARCH_SESSION_END = "research_session_end"
TOOL_RESEARCH_TRANSCRIPT_STORE = "research_transcript_store"
TOOL_RESEARCH_CAPTURE_STORE = "research_capture_store"
TOOL_RESEARCH_SEARCH = "research_search"

# Tier-specific tool name constants
TOOL_SEARCH_ENTITIES = "search_entities"
TOOL_SEARCH_FACTS = "search_facts"
TOOL_CODE_SEARCH = "code_search"
TOOL_SEARCH_FUNCTION = "search_function"
TOOL_SEARCH_CLASS = "search_class"

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
    TOOL_MEMORY_STATS,
    # Research tools
    TOOL_RESEARCH_SESSION_START,
    TOOL_RESEARCH_SESSION_END,
    TOOL_RESEARCH_TRANSCRIPT_STORE,
    TOOL_RESEARCH_CAPTURE_STORE,
    TOOL_RESEARCH_SEARCH,
    # Tier-specific tools
    TOOL_SEARCH_ENTITIES,
    TOOL_SEARCH_FACTS,
    TOOL_CODE_SEARCH,
    TOOL_SEARCH_FUNCTION,
    TOOL_SEARCH_CLASS
]
