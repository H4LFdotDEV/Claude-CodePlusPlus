# API Reference

Complete MCP tool schemas for Claude Code++ Memory MCP Server (20 tools).

## Tool Categories

| Category | Count | Description |
|----------|-------|-------------|
| Core | 10 | Memory CRUD, sessions, vault operations |
| Research | 5 | Voice/whiteboard research sessions |
| Tier-Specific | 5 | Knowledge graph and code search |

---

## Core Tools (10)

### memory_store

Store content in long-term memory.

```json
{
  "name": "memory_store",
  "parameters": {
    "content": {
      "type": "string",
      "description": "Content to store",
      "required": true
    },
    "type": {
      "type": "string",
      "enum": ["code", "note", "conversation", "reference"],
      "required": true
    },
    "source": {
      "type": "string",
      "description": "Source identifier",
      "required": true
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "required": false
    },
    "project": {
      "type": "string",
      "description": "Project name",
      "required": false
    }
  }
}
```

### memory_search

Multi-tier search using text or semantic similarity.

```json
{
  "name": "memory_search",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query",
      "required": true
    },
    "type": {
      "type": "string",
      "enum": ["text", "semantic", "hybrid"],
      "required": false,
      "default": "hybrid"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 100)",
      "required": false,
      "default": 10
    },
    "filters": {
      "type": "object",
      "properties": {
        "doc_type": {"type": "string"},
        "project": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}}
      },
      "required": false
    }
  }
}
```

**Multi-tier behavior (when `type="hybrid"` or `type="semantic"`):**
1. Hot tier (Redis) - Cached results
2. Warm tier (Graphiti) - Entity matches
3. Cold tier (SQLite) - Full-text search
4. Cold tier (livegrep) - Code matches
5. Results deduplicated and filtered

### memory_recall

Recall a specific memory by ID. **Tracks access for tier promotion** (5+ accesses triggers warm tier promotion).

```json
{
  "name": "memory_recall",
  "parameters": {
    "id": {
      "type": "string",
      "description": "Document ID",
      "required": true
    }
  }
}
```

### memory_delete

Delete a memory from all tiers.

```json
{
  "name": "memory_delete",
  "parameters": {
    "id": {
      "type": "string",
      "description": "Document ID to delete",
      "required": true
    }
  }
}
```

### memory_list

List recent memories with optional filters.

```json
{
  "name": "memory_list",
  "parameters": {
    "type": {
      "type": "string",
      "description": "Filter by type",
      "required": false
    },
    "project": {
      "type": "string",
      "description": "Filter by project",
      "required": false
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 100)",
      "required": false,
      "default": 20
    }
  }
}
```

### session_save

Save current session state.

```json
{
  "name": "session_save",
  "parameters": {
    "project_path": {
      "type": "string",
      "description": "Project directory path",
      "required": true
    },
    "active_files": {
      "type": "array",
      "items": {"type": "string"},
      "required": false
    },
    "context": {
      "type": "object",
      "description": "Additional context",
      "required": false
    }
  }
}
```

### session_restore

Restore a previous session.

```json
{
  "name": "session_restore",
  "parameters": {
    "session_id": {
      "type": "string",
      "description": "Session ID (optional, restores latest if omitted)",
      "required": false
    }
  }
}
```

### vault_write

Write a note to the Obsidian vault.

```json
{
  "name": "vault_write",
  "parameters": {
    "path": {
      "type": "string",
      "description": "Note path (without .md)",
      "required": true
    },
    "content": {
      "type": "string",
      "description": "Note content",
      "required": true
    },
    "folder": {
      "type": "string",
      "enum": ["code", "notes", "conversations", "references", "daily"],
      "required": false
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "required": false
    }
  }
}
```

### vault_read

Read a note from the vault.

```json
{
  "name": "vault_read",
  "parameters": {
    "path": {
      "type": "string",
      "description": "Note path",
      "required": true
    }
  }
}
```

### memory_stats

Get memory system statistics with tier health checks.

```json
{
  "name": "memory_stats",
  "parameters": {}
}
```

**Returns:**
```json
{
  "sqlite_count": 1234,
  "session_id": "current-session-id",
  "components": {
    "sqlite": true,
    "vault": true,
    "redis": true,
    "embedder": true,
    "tier_manager": true
  },
  "health": {
    "sqlite": {"status": "healthy", "latency_ms": 5},
    "vault": {"status": "connected", "latency_ms": 15},
    "redis": {"status": "healthy", "latency_ms": 1},
    "embedder": {"status": "active"},
    "tier_manager": {
      "status": "healthy",
      "latency_ms": 8,
      "available_tiers": ["hot", "warm", "cold", "code_search"]
    }
  },
  "tiers": {
    "hot": {"available": true, "stats": {...}},
    "warm": {"available": true, "stats": {...}},
    "cold": {"available": true, "stats": {...}},
    "code_search": {"available": true, "stats": {...}}
  }
}
```

---

## Research Tools (5)

### research_session_start

Start a new research session for voice/whiteboard capture.

```json
{
  "name": "research_session_start",
  "parameters": {
    "name": {
      "type": "string",
      "description": "Session name",
      "required": true
    },
    "focus_area": {
      "type": "string",
      "description": "Research focus or topic",
      "required": false
    },
    "participants": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of participant names",
      "required": false
    }
  }
}
```

### research_session_end

End a research session and generate summary.

```json
{
  "name": "research_session_end",
  "parameters": {
    "session_id": {
      "type": "string",
      "description": "Session ID to end",
      "required": true
    },
    "summary": {
      "type": "string",
      "description": "Session summary",
      "required": false
    },
    "action_items": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of action items",
      "required": false
    },
    "key_decisions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Key decisions made",
      "required": false
    }
  }
}
```

### research_transcript_store

Store a voice transcript segment.

```json
{
  "name": "research_transcript_store",
  "parameters": {
    "text": {
      "type": "string",
      "description": "Transcript text",
      "required": true
    },
    "speaker": {
      "type": "string",
      "description": "Speaker name",
      "required": false,
      "default": "user"
    },
    "session_id": {
      "type": "string",
      "description": "Associated research session",
      "required": false
    },
    "timestamp": {
      "type": "string",
      "description": "ISO timestamp of the segment",
      "required": false
    }
  }
}
```

### research_capture_store

Store a whiteboard or webcam capture.

```json
{
  "name": "research_capture_store",
  "parameters": {
    "description": {
      "type": "string",
      "description": "Description of what was captured",
      "required": true
    },
    "ocr_text": {
      "type": "string",
      "description": "Extracted text from the image",
      "required": false
    },
    "image_path": {
      "type": "string",
      "description": "Path to the image file",
      "required": false
    },
    "session_id": {
      "type": "string",
      "description": "Associated research session",
      "required": false
    },
    "capture_type": {
      "type": "string",
      "enum": ["whiteboard", "webcam", "screenshot"],
      "required": false,
      "default": "whiteboard"
    }
  }
}
```

### research_search

Search across research data.

```json
{
  "name": "research_search",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query",
      "required": true
    },
    "session_id": {
      "type": "string",
      "description": "Filter to specific session",
      "required": false
    },
    "type": {
      "type": "string",
      "enum": ["transcript", "research_image", "research_session"],
      "description": "Filter by content type",
      "required": false
    },
    "limit": {
      "type": "integer",
      "required": false,
      "default": 20
    }
  }
}
```

---

## Tier-Specific Tools (5)

### search_entities

Search Graphiti knowledge graph for entities.

```json
{
  "name": "search_entities",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query for entities",
      "required": true
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 100)",
      "required": false,
      "default": 10
    }
  }
}
```

**Returns:**
```json
{
  "results": [
    {
      "id": "entity-uuid",
      "name": "EntityName",
      "summary": "Entity description",
      "labels": ["Label1", "Label2"]
    }
  ],
  "total": 1
}
```

### search_facts

Search Graphiti knowledge graph for facts/relationships.

```json
{
  "name": "search_facts",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query for facts",
      "required": true
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 100)",
      "required": false,
      "default": 10
    }
  }
}
```

**Returns:**
```json
{
  "results": [
    {
      "id": "fact-uuid",
      "source": "SourceEntity",
      "target": "TargetEntity",
      "fact": "The relationship between them",
      "valid_at": "2024-01-15",
      "invalid_at": null
    }
  ],
  "total": 1
}
```

### code_search

Search code across repositories using RE2 regex patterns via livegrep.

```json
{
  "name": "code_search",
  "parameters": {
    "query": {
      "type": "string",
      "description": "RE2 regex pattern",
      "required": true
    },
    "path_filter": {
      "type": "string",
      "description": "Glob pattern to filter files (e.g., '*.py')",
      "required": false
    },
    "repo_filter": {
      "type": "string",
      "description": "Repository name to search within",
      "required": false
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 200)",
      "required": false,
      "default": 50
    }
  }
}
```

**Returns:**
```json
{
  "results": [
    {
      "repo": "repository-name",
      "path": "src/file.ts",
      "line_number": 42,
      "line_content": "matching line content"
    }
  ],
  "total": 1,
  "truncated": false,
  "duration_ms": 15
}
```

### search_function

Search for function/method definitions by name.

```json
{
  "name": "search_function",
  "parameters": {
    "name": {
      "type": "string",
      "description": "Function name to search for",
      "required": true
    },
    "language": {
      "type": "string",
      "description": "Programming language (python, javascript, typescript, go, rust, java, c, cpp)",
      "required": false
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 200)",
      "required": false,
      "default": 50
    }
  }
}
```

**Language patterns used:**
| Language | Pattern |
|----------|---------|
| python | `def name` or `async def name` |
| javascript/typescript | `function name` or `const name =` |
| go | `func name` or `func (receiver) name` |
| rust | `fn name` or `pub fn name` |
| java | `void name` or `public ... name` |
| c/cpp | Return type followed by `name(` |

### search_class

Search for class/struct/interface definitions by name.

```json
{
  "name": "search_class",
  "parameters": {
    "name": {
      "type": "string",
      "description": "Class/struct name to search for",
      "required": true
    },
    "language": {
      "type": "string",
      "description": "Programming language (python, javascript, typescript, go, rust, java)",
      "required": false
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (max: 200)",
      "required": false,
      "default": 50
    }
  }
}
```

**Language patterns used:**
| Language | Pattern |
|----------|---------|
| python | `class name` |
| javascript/typescript | `class name` or `interface name` |
| go | `type name struct` |
| rust | `struct name` or `impl name` |
| java | `class name` or `interface name` |

---

## Response Format

All tools return JSON responses wrapped in MCP content format:

**Success:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{...}"
    }
  ]
}
```

**Error:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error message"
    }
  ],
  "isError": true
}
```

## Validation

Input validation is performed on all parameters:

- **String fields**: Length limits enforced (typically 1-10000 chars for content)
- **Limit fields**: Clamped to maximum values (100 for most, 200 for code search)
- **Enum fields**: Invalid values rejected with clear error message
- **Required fields**: Missing required fields return validation error

## Timeouts

Async operations use configurable timeouts:

| Operation | Default Timeout |
|-----------|-----------------|
| General async | 30 seconds |
| Graphiti search | 30 seconds |
| Tier promotion | 60 seconds |

## Related Pages

- [[Memory-MCP-Tools]] - Tool usage examples
- [[Memory-MCP]] - Memory system overview
- [[Memory-Tiers]] - Tier architecture
- [[Configuration]] - Setup options
