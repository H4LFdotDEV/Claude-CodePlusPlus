# API Reference

Complete MCP tool schemas for Claude Code++.

## Memory MCP Tools

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

Search memory using text or semantic similarity.

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
      "description": "Maximum results",
      "required": false,
      "default": 10
    }
  }
}
```

### memory_list

List recent memories.

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
      "required": false,
      "default": 20
    }
  }
}
```

### memory_recall

Recall a specific memory by ID.

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

Delete a memory.

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

Get memory system statistics.

```json
{
  "name": "memory_stats",
  "parameters": {}
}
```

**Returns:**
```json
{
  "components": {
    "sqlite": true,
    "redis": true,
    "lancedb": true,
    "graphiti": false,
    "livegrep": false,
    "vault": true
  },
  "counts": {
    "total_documents": 1234,
    "by_type": {
      "code": 500,
      "note": 400,
      "conversation": 200,
      "reference": 134
    }
  },
  "health": {
    "status": "healthy",
    "latency_ms": {
      "sqlite": 5,
      "redis": 1,
      "lancedb": 8
    }
  }
}
```

## Knowledge Graph Tools

### search_entities

Search knowledge graph for entities.

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
      "required": false,
      "default": 10
    }
  }
}
```

### search_facts

Search knowledge graph for facts/relationships.

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
      "required": false,
      "default": 10
    }
  }
}
```

## Code Search Tools

### code_search

Search code across repositories using regex patterns.

```json
{
  "name": "code_search",
  "parameters": {
    "query": {
      "type": "string",
      "description": "RE2 regex pattern",
      "required": true
    },
    "repo_filter": {
      "type": "string",
      "description": "Filter by repository name",
      "required": false
    },
    "path_filter": {
      "type": "string",
      "description": "Filter by file path (e.g., '*.py')",
      "required": false
    },
    "max_matches": {
      "type": "integer",
      "required": false,
      "default": 50
    }
  }
}
```

### search_function

Search for function/method definitions.

```json
{
  "name": "search_function",
  "parameters": {
    "function_name": {
      "type": "string",
      "description": "Name of function to find",
      "required": true
    },
    "language": {
      "type": "string",
      "description": "Programming language",
      "required": false
    },
    "max_matches": {
      "type": "integer",
      "required": false,
      "default": 20
    }
  }
}
```

### search_class

Search for class/struct/interface definitions.

```json
{
  "name": "search_class",
  "parameters": {
    "class_name": {
      "type": "string",
      "description": "Name of class to find",
      "required": true
    },
    "language": {
      "type": "string",
      "description": "Programming language",
      "required": false
    },
    "max_matches": {
      "type": "integer",
      "required": false,
      "default": 20
    }
  }
}
```

## Response Format

All tools return JSON responses:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Error responses:

```json
{
  "success": false,
  "data": null,
  "error": "Error message describing what went wrong"
}
```

## Related Pages

- [[Memory-MCP-Tools]] - Tool usage examples
- [[Memory-MCP]] - Memory system overview
- [[Configuration]] - Setup options
