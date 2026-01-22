# Memory MCP

The Memory MCP server provides persistent context management for Claude Code++, enabling Claude to genuinely remember past interactions, preferences, and decisions.

## Overview

Traditional AI assistants are stateless - each conversation starts fresh. Memory MCP changes this by providing:

- **Persistent Storage**: Information survives across sessions
- **Intelligent Retrieval**: Semantic search finds relevant context
- **Tiered Architecture**: Optimized for different access patterns
- **Session Continuity**: Resume exactly where you left off

## Quick Start

### Check Memory Status
```
memory_stats
```

Returns component availability and document counts.

### Store Something
```
memory_store(
  content="User prefers TypeScript over JavaScript",
  type="note",
  source="conversation:2024-01-15",
  tags=["preference", "language"]
)
```

### Search Memory
```
memory_search(query="TypeScript preference", type="hybrid")
```

### Save Session
```
session_save(project_path="/path/to/project")
```

## Core Concepts

### Document Types

| Type | Use Case | Examples |
|------|----------|----------|
| `code` | Code snippets, implementations | Functions, classes, patterns |
| `note` | General notes, observations | Preferences, reminders |
| `conversation` | Conversation excerpts | Important discussions |
| `reference` | Reference material | Documentation, decisions |

### Tags

Tags enable filtered retrieval:
- Project tags: `api-gateway`, `frontend`, `mobile`
- Category tags: `preference`, `decision`, `error`, `solution`
- Technical tags: `typescript`, `react`, `auth`

### Projects

Associate memories with specific projects for scoped retrieval:
```
memory_search(
  query="auth implementation",
  filters={"project": "api-gateway"}
)
```

## Memory Lifecycle

### Creation
1. Claude identifies important information
2. Calls `memory_store` with appropriate type/tags
3. Content stored in SQLite (metadata) + appropriate tier
4. Embeddings generated if provider available

### Retrieval
1. Query triggers search across tiers
2. Results merged and ranked
3. Access timestamps updated
4. Frequently accessed items promoted

### Update
1. Search for existing memory
2. Delete outdated version
3. Store corrected version
4. References maintained via tags

### Deletion
1. `memory_delete` removes from all tiers
2. Cascades through storage backends
3. Embeddings removed if present

## Tool Reference

See [[Memory-MCP-Tools]] for detailed tool documentation.

| Tool | Purpose |
|------|---------|
| `memory_store` | Store new memories |
| `memory_search` | Search across all tiers |
| `memory_recall` | Retrieve by ID |
| `memory_delete` | Remove memories |
| `memory_list` | List with filters |
| `session_save` | Persist session state |
| `session_restore` | Load session state |
| `vault_write` | Write to Obsidian vault |
| `vault_read` | Read from Obsidian vault |
| `memory_stats` | Health and statistics |

## Behavioral Guidelines

See [[Memory-MCP-Behavioral-Guidelines]] for how Claude should use memory.

Key principles:
- **Search-first**: Always search before answering context questions
- **Store selectively**: Preferences, decisions, solutions - not everything
- **Update proactively**: Delete outdated info when things change
- **Organize by project**: Use consistent project tags

## Tier Architecture

See [[Memory-Tiers]] for detailed tier documentation.

| Tier | When to Use |
|------|-------------|
| Hot (Redis) | Current session context |
| Warm (Graphiti) | Relationship queries ("how does X relate to Y?") |
| Warm (LanceDB) | Semantic similarity ("find similar errors") |
| Cold (SQLite) | Full-text search, metadata queries |
| Cold (livegrep) | Code search across repositories |
| Archive (Vault) | Human-readable documentation |

## Configuration

### Environment Variables

```bash
# Logging
MEMORY_MCP_LOG_LEVEL=INFO
MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/memory.log

# Storage paths
SQLITE_PATH=~/.claude-code-pp/memory/sqlite/memories.db
OBSIDIAN_VAULT_PATH=~/.claude-code-pp/memory/vault

# Optional services
REDIS_URL=redis://localhost:6379
NEO4J_URI=bolt://localhost:7687
```

### MCP Server Configuration

In `~/.claude.json`:
```json
{
  "mcpServers": {
    "memory": {
      "command": "/path/to/memory-mcp",
      "args": [],
      "env": {
        "REDIS_URL": "redis://localhost:6379"
      }
    }
  }
}
```

## Examples

### Storing User Preferences
```python
memory_store(
  content="User prefers: dark mode, vim keybindings, 2-space indent",
  type="note",
  source="preferences:editor",
  tags=["preference", "editor", "settings"],
  project="user-profile"
)
```

### Storing Error Solutions
```python
memory_store(
  content="""
  Error: ECONNREFUSED on Redis connection
  Cause: Redis not running
  Solution: brew services start redis
  """,
  type="reference",
  source="troubleshooting:redis",
  tags=["error", "redis", "solution"]
)
```

### Storing Architecture Decisions
```python
memory_store(
  content="""
  Decision: Use JWT for authentication
  Rationale: Stateless scaling, microservices compatible
  Trade-offs: Need refresh token rotation strategy
  Date: 2024-01-15
  """,
  type="reference",
  source="architecture:auth",
  tags=["decision", "architecture", "auth", "jwt"],
  project="api-gateway"
)
```

### Session Workflow
```python
# Start of session
session_restore()
memory_list(limit=10)  # Recent context

# During work
memory_search(query="auth middleware implementation")
# ... work on code ...
memory_store(content="Implemented rate limiting", ...)

# End of session
session_save(
  project_path="/Users/dev/api-gateway",
  active_files=["src/auth/middleware.ts"],
  context={"current_task": "rate limiting"}
)
```

## Related Pages

- [[Memory-MCP-Tools]] - Complete tool reference
- [[Memory-MCP-Behavioral-Guidelines]] - Usage patterns
- [[Memory-Tiers]] - Tier deep dive
- [[Troubleshooting]] - Common issues
