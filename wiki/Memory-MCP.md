# Memory MCP

The Memory MCP server provides persistent context management for Claude Code++, enabling Claude to genuinely remember past interactions, preferences, and decisions.

## Overview

Traditional AI assistants are stateless - each conversation starts fresh. Memory MCP changes this by providing:

- **Persistent Storage**: Information survives across sessions
- **Intelligent Retrieval**: Multi-tier search finds relevant context
- **Tiered Architecture**: Optimized for different access patterns
- **Session Continuity**: Resume exactly where you left off
- **Knowledge Graph**: Entity relationships and fact tracking
- **Code Search**: Cross-repository code search via livegrep

## Quick Start

### Check Memory Status
```
memory_stats
```

Returns component availability, tier health, and document counts.

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

Uses multi-tier search across Redis, Graphiti, SQLite, and livegrep.

### Search Knowledge Graph
```
search_entities(query="user preferences")
search_facts(query="decided to use JWT")
```

### Search Code
```
code_search(query="async function.*authenticate", path_filter="*.ts")
search_function(name="authenticateRequest", language="typescript")
```

### Save Session
```
session_save(project_path="/path/to/project")
```

## Tool Categories

Memory MCP provides **20 tools** across three categories:

### Core Tools (10)

| Tool | Purpose |
|------|---------|
| `memory_store` | Store new memories |
| `memory_search` | Multi-tier search |
| `memory_recall` | Retrieve by ID (tracks access) |
| `memory_delete` | Remove memories |
| `memory_list` | List with filters |
| `session_save` | Persist session state |
| `session_restore` | Load session state |
| `vault_write` | Write to Obsidian vault |
| `vault_read` | Read from Obsidian vault |
| `memory_stats` | Health and statistics |

### Research Tools (5)

| Tool | Purpose |
|------|---------|
| `research_session_start` | Start voice/whiteboard session |
| `research_session_end` | End session with summary |
| `research_transcript_store` | Store voice transcripts |
| `research_capture_store` | Store whiteboard captures |
| `research_search` | Search research data |

### Tier-Specific Tools (5)

| Tool | Purpose |
|------|---------|
| `search_entities` | Search Graphiti knowledge graph for entities |
| `search_facts` | Search Graphiti for facts/relationships |
| `code_search` | RE2 regex code search via livegrep |
| `search_function` | Find function definitions |
| `search_class` | Find class/struct definitions |

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
4. Vault note created for code/notes
5. Redis cache updated if available

### Retrieval
1. Query triggers multi-tier search
2. Results from Redis, Graphiti, SQLite, livegrep merged
3. Results deduplicated and ranked
4. Access timestamps updated
5. Frequently accessed items promoted to warm tier

### Access Tracking and Promotion
1. Each `memory_recall` tracks access via AccessTracker
2. AccessTracker uses LRU cache (max 10k entries)
3. After 5+ accesses, document promoted to Graphiti
4. Entity extraction adds document to knowledge graph

### Update
1. Search for existing memory
2. Delete outdated version
3. Store corrected version
4. References maintained via tags

### Deletion
1. `memory_delete` removes from all tiers
2. Cascades through storage backends
3. Access tracking cleared

## Tier Architecture

See [[Memory-Tiers]] for detailed tier documentation.

| Tier | Storage | Access Time | When to Use |
|------|---------|-------------|-------------|
| Hot | Redis | <1ms | Current session context |
| Warm | Graphiti | <50ms | Relationship queries |
| Cold | SQLite | <50ms | Full-text search |
| Cold | livegrep | <100ms | Code search |
| Archive | Vault | <200ms | Human-readable docs |

### Multi-Tier Search

When using `memory_search` with `type="hybrid"` or `type="semantic"`:

1. **Hot tier** (Redis) - Cached query results
2. **Warm tier** (Graphiti) - Entity and fact matches
3. **Cold tier** (SQLite) - Full-text search results
4. **Cold tier** (livegrep) - Code search results

Results are deduplicated, merged, and filtered by tags/project.

### Tier-Specific Tools

Use dedicated tools for specific tier operations:

- **Graphiti**: `search_entities`, `search_facts`
- **livegrep**: `code_search`, `search_function`, `search_class`

## Behavioral Guidelines

See [[Memory-MCP-Behavioral-Guidelines]] for how Claude should use memory.

Key principles:
- **Search-first**: Always search before answering context questions
- **Store selectively**: Preferences, decisions, solutions - not everything
- **Update proactively**: Delete outdated info when things change
- **Organize by project**: Use consistent project tags
- **Use tier tools**: Use `search_entities` for relationships, `code_search` for code

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
LIVEGREP_URL=http://localhost:8910
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
        "REDIS_URL": "redis://localhost:6379",
        "NEO4J_URI": "bolt://localhost:7687",
        "LIVEGREP_URL": "http://localhost:8910"
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
search_function(name="authenticateRequest", language="typescript")
# ... work on code ...
memory_store(content="Implemented rate limiting", ...)

# End of session
session_save(
  project_path="/Users/dev/api-gateway",
  active_files=["src/auth/middleware.ts"],
  context={"current_task": "rate limiting"}
)
```

### Knowledge Graph Queries
```python
# Find entities
search_entities(query="user coding preferences", limit=10)

# Find relationships
search_facts(query="authentication decisions", limit=10)
```

### Code Search
```python
# Regex search
code_search(
  query="async function.*validate",
  path_filter="*.ts",
  repo_filter="api-gateway"
)

# Function definition
search_function(name="validateToken", language="typescript")

# Class definition
search_class(name="AuthMiddleware", language="typescript")
```

## Research Sessions

For voice conversations and whiteboard capture:

```python
# Start session
research_session_start(
  name="API Design Discussion",
  focus_area="REST vs GraphQL",
  participants=["Jeremiah", "Claude"]
)

# Store transcripts as they come in
research_transcript_store(
  text="I think we should use GraphQL for the query complexity",
  speaker="Jeremiah",
  session_id="session-uuid"
)

# Store whiteboard captures
research_capture_store(
  description="Architecture diagram with GraphQL layer",
  ocr_text="Client -> GraphQL -> REST APIs",
  session_id="session-uuid",
  capture_type="whiteboard"
)

# End session
research_session_end(
  session_id="session-uuid",
  summary="Decided on GraphQL for complex queries",
  action_items=["Create GraphQL schema", "Set up Apollo Server"],
  key_decisions=["GraphQL for reads, REST for mutations"]
)

# Search later
research_search(query="GraphQL decision", type="transcript")
```

## Module Structure

```
memory_mcp/
├── server.py              # MCP protocol server
├── tier_manager.py        # Multi-tier orchestration
├── access_tracker.py      # LRU access tracking
├── async_utils.py         # Async/sync bridging with timeout
├── handlers/
│   ├── memory.py          # Core CRUD operations
│   ├── session.py         # Session save/restore
│   ├── vault.py           # Vault read/write
│   ├── stats.py           # Health and statistics
│   ├── research.py        # Research session tools
│   └── tier.py            # Knowledge graph and code search
├── sqlite_index.py        # SQLite storage layer
├── redis_client.py        # Redis hot cache
├── graphiti_manager.py    # Graphiti knowledge graph
├── livegrep_client.py     # livegrep code search
├── vault_manager.py       # Obsidian vault integration
└── tool_schemas.py        # MCP tool schema definitions
```

## Related Pages

- [[Memory-MCP-Tools]] - Complete tool reference (all 20 tools)
- [[Memory-MCP-Behavioral-Guidelines]] - Usage patterns
- [[Memory-Tiers]] - Tier deep dive with promotion logic
- [[Troubleshooting]] - Common issues
