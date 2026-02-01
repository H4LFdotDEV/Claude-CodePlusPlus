# Memory MCP Server

Tiered memory system for Claude Code++ with Redis, Graphiti/Neo4j, SQLite, livegrep, and Obsidian vault integration.

## Installation

```bash
# Basic installation (SQLite + Obsidian only)
pip install -e .

# With Redis hot cache
pip install -e ".[redis]"

# With Graphiti knowledge graph
pip install -e ".[graphiti]"

# With livegrep code search
pip install -e ".[livegrep]"

# Full installation (all features)
pip install -e ".[all]"

# Development dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# Start the MCP server
python -m memory_mcp.server

# Or use the installed command
memory-mcp
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Protocol Layer                        │
│                  (JSON-RPC 2.0 over stdio)                   │
├─────────────────────────────────────────────────────────────┤
│  Handler Layer                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ MemoryHandler │ SessionHandler │ VaultHandler        │   │
│  │ StatsHandler  │ ResearchHandler │ TierHandler        │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  TierManager (orchestrates multi-tier operations)           │
│  AccessTracker (LRU cache, max 10k entries)                 │
├─────────────────────────────────────────────────────────────┤
│  Memory Tiers                                                │
│  ┌─────────┐  ┌───────────┐  ┌─────────┐  ┌──────────────┐ │
│  │  Redis  │→ │ Graphiti  │→ │ SQLite  │→ │ Obsidian     │ │
│  │  (Hot)  │  │  (Warm)   │  │ (Cold)  │  │   (Archive)  │ │
│  │  <1ms   │  │  <50ms    │  │  <50ms  │  │    <200ms    │ │
│  └─────────┘  └───────────┘  └─────────┘  └──────────────┘ │
│                               ┌──────────┐                  │
│                               │ livegrep │ (Code Search)    │
│                               │  <100ms  │                  │
│                               └──────────┘                  │
├─────────────────────────────────────────────────────────────┤
│  Async Utilities (run_async with configurable timeout)      │
└─────────────────────────────────────────────────────────────┘
```

### Tier Behavior

| Tier | Storage | Access Time | Capacity | Automatic |
|------|---------|-------------|----------|-----------|
| Hot | Redis | <1ms | 1000 items | Session cache |
| Warm | Graphiti/Neo4j | <50ms | Relationship-based | Knowledge graph |
| Cold | SQLite | <50ms | Unlimited | All metadata |
| Cold | livegrep | <100ms | All indexed repos | Code search |
| Archive | Obsidian | <200ms | Unlimited | Human-readable |

Components gracefully degrade if unavailable:
- No Redis → Skip hot cache
- No Graphiti → Skip knowledge graph queries
- No livegrep → Skip code search
- No embeddings → Skip semantic search

### Automatic Tier Promotion

Documents accessed 5+ times are automatically promoted to the warm tier (Graphiti knowledge graph). The access tracker uses:
- LRU eviction with max 10,000 entries
- Redis distributed tracking when available
- Local in-memory fallback

## MCP Tools (20 Total)

### Core Tools (10)

#### memory_store
Store content in long-term memory.

```json
{
  "name": "memory_store",
  "arguments": {
    "content": "Function to calculate fibonacci sequence",
    "type": "code",
    "source": "src/utils/math.ts",
    "tags": ["algorithm", "recursion"],
    "project": "my-project"
  }
}
```

**Parameters:**
- `content` (required): Content to store
- `type` (required): `code` | `note` | `conversation` | `reference`
- `source` (required): Source identifier (file path, URL)
- `tags` (optional): Array of tags
- `project` (optional): Project name

#### memory_search
Search memory using text or semantic similarity. Uses multi-tier search when available.

```json
{
  "name": "memory_search",
  "arguments": {
    "query": "fibonacci algorithm",
    "type": "hybrid",
    "limit": 10,
    "filters": {
      "doc_type": "code",
      "project": "my-project",
      "tags": ["algorithm"]
    }
  }
}
```

**Parameters:**
- `query` (required): Search query
- `type` (optional): `text` | `semantic` | `hybrid` (default: hybrid)
- `limit` (optional): Max results (default: 10, max: 100)
- `filters` (optional): Filter by doc_type, project, or tags

#### memory_recall
Recall a specific memory by ID. Tracks access for tier promotion (5+ accesses triggers warm tier promotion).

```json
{
  "name": "memory_recall",
  "arguments": {
    "id": "abc123def456"
  }
}
```

#### memory_delete
Delete a memory by ID.

```json
{
  "name": "memory_delete",
  "arguments": {
    "id": "abc123def456"
  }
}
```

#### memory_list
List recent memories with optional filters.

```json
{
  "name": "memory_list",
  "arguments": {
    "limit": 20,
    "type": "code",
    "project": "my-project"
  }
}
```

#### session_save
Save current session state for later restoration.

```json
{
  "name": "session_save",
  "arguments": {
    "project_path": "/Users/me/projects/my-app",
    "active_files": ["src/index.ts", "src/utils.ts"],
    "context": {"last_task": "implementing auth"}
  }
}
```

#### session_restore
Restore a previous session.

```json
{
  "name": "session_restore",
  "arguments": {
    "session_id": "uuid-of-session"
  }
}
```

#### vault_write
Write a note to the Obsidian vault.

```json
{
  "name": "vault_write",
  "arguments": {
    "path": "project-notes/api-design",
    "content": "# API Design\n\nEndpoints:\n- GET /users\n- POST /users",
    "folder": "notes",
    "tags": ["api", "design"]
  }
}
```

#### vault_read
Read a note from the Obsidian vault.

```json
{
  "name": "vault_read",
  "arguments": {
    "path": "notes/project-notes/api-design"
  }
}
```

#### memory_stats
Get memory system statistics with tier health checks.

```json
{
  "name": "memory_stats",
  "arguments": {}
}
```

Returns:
```json
{
  "sqlite_count": 1523,
  "session_id": "current-session-id",
  "components": {
    "sqlite": true,
    "vault": true,
    "redis": true,
    "embedder": true,
    "tier_manager": true
  },
  "health": {
    "sqlite": {"status": "healthy", "latency_ms": 2.5},
    "vault": {"status": "connected", "latency_ms": 15.3},
    "redis": {"status": "healthy", "latency_ms": 0.8},
    "tier_manager": {"status": "healthy", "available_tiers": ["hot", "warm", "cold"]}
  },
  "tiers": {
    "hot": {"available": true, "stats": {...}},
    "warm": {"available": true, "stats": {...}},
    "cold": {"available": true, "stats": {...}},
    "code_search": {"available": true, "stats": {...}}
  }
}
```

### Research Tools (5)

#### research_session_start
Start a new research session for voice/whiteboard capture.

```json
{
  "name": "research_session_start",
  "arguments": {
    "name": "Pocket Dimension Physics",
    "focus_area": "Quantum mechanics fundamentals",
    "participants": ["Jeremiah", "Claude"]
  }
}
```

#### research_session_end
End a research session and generate summary.

```json
{
  "name": "research_session_end",
  "arguments": {
    "session_id": "uuid-of-session",
    "summary": "Explored quantum entanglement concepts",
    "action_items": ["Research Bell's theorem", "Create visualization"],
    "key_decisions": ["Focus on practical applications"]
  }
}
```

#### research_transcript_store
Store a voice transcript segment.

```json
{
  "name": "research_transcript_store",
  "arguments": {
    "text": "The key insight here is that quantum states can be correlated...",
    "speaker": "Jeremiah",
    "session_id": "uuid-of-session",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

#### research_capture_store
Store a whiteboard or webcam capture.

```json
{
  "name": "research_capture_store",
  "arguments": {
    "description": "Diagram showing quantum state superposition",
    "ocr_text": "State |psi> = alpha|0> + beta|1>",
    "image_path": "/path/to/capture.png",
    "session_id": "uuid-of-session",
    "capture_type": "whiteboard"
  }
}
```

#### research_search
Search across research data.

```json
{
  "name": "research_search",
  "arguments": {
    "query": "quantum entanglement",
    "session_id": "optional-session-id",
    "type": "transcript",
    "limit": 20
  }
}
```

### Tier-Specific Tools (5)

#### search_entities
Search Graphiti knowledge graph for entities.

```json
{
  "name": "search_entities",
  "arguments": {
    "query": "user preferences",
    "limit": 10
  }
}
```

Returns:
```json
{
  "results": [
    {
      "id": "entity-uuid",
      "name": "UserPreferences",
      "summary": "User's coding preferences and settings",
      "labels": ["User", "Preference"]
    }
  ],
  "total": 1
}
```

#### search_facts
Search Graphiti knowledge graph for facts/relationships.

```json
{
  "name": "search_facts",
  "arguments": {
    "query": "decided to use JWT",
    "limit": 10
  }
}
```

Returns:
```json
{
  "results": [
    {
      "id": "fact-uuid",
      "source": "Project",
      "target": "JWT",
      "fact": "Project decided to use JWT for authentication",
      "valid_at": "2024-01-15",
      "invalid_at": null
    }
  ],
  "total": 1
}
```

#### code_search
Search code using RE2 regex via livegrep.

```json
{
  "name": "code_search",
  "arguments": {
    "query": "async function.*authenticate",
    "path_filter": "*.ts",
    "repo_filter": "api-gateway",
    "limit": 50
  }
}
```

Returns:
```json
{
  "results": [
    {
      "repo": "api-gateway",
      "path": "src/auth/middleware.ts",
      "line_number": 42,
      "line_content": "async function authenticateRequest(req, res, next) {"
    }
  ],
  "total": 1,
  "truncated": false,
  "duration_ms": 15
}
```

#### search_function
Find function or method definitions by name.

```json
{
  "name": "search_function",
  "arguments": {
    "name": "authenticateRequest",
    "language": "typescript",
    "limit": 50
  }
}
```

**Supported languages:** python, javascript, typescript, go, rust, java, c, cpp

#### search_class
Find class, struct, or interface definitions by name.

```json
{
  "name": "search_class",
  "arguments": {
    "name": "AuthMiddleware",
    "language": "typescript",
    "limit": 50
  }
}
```

**Supported languages:** python, javascript, typescript, go, rust, java

## Configuration

### Environment Variables

```bash
# Storage paths
MEMORY_SQLITE_PATH=~/.claude-code-pp/memory/memories.db
OBSIDIAN_VAULT_PATH=~/Documents/ObsidianVault

# Redis (hot tier)
REDIS_URL=redis://localhost:6379

# Graphiti (warm tier - knowledge graph)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# livegrep (cold tier - code search)
LIVEGREP_URL=http://localhost:8910

# Embedding providers (in order of preference)
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...
VOYAGE_API_KEY=pa-...

# Logging
MEMORY_MCP_LOG_LEVEL=INFO
MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/memory.log
```

### Config File

Create `~/.claude-code-pp/config/settings.yaml`:

```yaml
memory:
  sqlite:
    path: ~/.claude-code-pp/memory/memories.db
  redis:
    url: redis://localhost:6379
    ttl: 3600
  graphiti:
    neo4j_uri: bolt://localhost:7687
    neo4j_user: neo4j
    neo4j_password: password
  livegrep:
    url: http://localhost:8910
  vault:
    path: ~/Documents/ObsidianVault

embeddings:
  providers:
    - type: ollama
      model: nomic-embed-text
      base_url: http://localhost:11434
    - type: openai
      model: text-embedding-3-small
    - type: voyage
      model: voyage-code-2

tier_promotion:
  threshold: 5  # Access count to trigger promotion
  min_size: 100  # Minimum content size for entity extraction
  demotion_ttl_hours: 168  # 1 week without access before demotion

access_tracker:
  max_cache_size: 10000  # LRU eviction limit
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=memory_mcp --cov-report=term-missing

# Run specific test file
pytest tests/test_server.py -v

# Run handler tests
pytest tests/test_handlers.py -v

# Run tier flow tests
pytest tests/test_tier_flow.py -v
```

## Development

```bash
# Format code
black memory_mcp/

# Lint
ruff check memory_mcp/

# Type checking
mypy memory_mcp/
```

## Module Structure

```
memory_mcp/
├── __init__.py
├── server.py              # MCP protocol server
├── config.py              # Configuration management
├── sqlite_index.py        # SQLite storage layer
├── redis_client.py        # Redis hot cache
├── graphiti_manager.py    # Graphiti knowledge graph
├── livegrep_client.py     # livegrep code search
├── vault_manager.py       # Obsidian vault integration
├── embedding_provider.py  # Embedding providers
├── tier_manager.py        # Multi-tier orchestration
├── access_tracker.py      # Access pattern tracking (LRU)
├── async_utils.py         # Async/sync bridging with timeout
├── stats_collector.py     # Performance metrics
├── validation.py          # Input validation
├── tool_schemas.py        # MCP tool schema definitions
├── SYSTEM_PROMPT.md       # Behavioral guidelines
└── handlers/
    ├── __init__.py
    ├── base.py            # Base handler class
    ├── memory.py          # Core CRUD operations
    ├── session.py         # Session save/restore
    ├── vault.py           # Vault read/write
    ├── stats.py           # Statistics and health
    ├── research.py        # Research session tools
    └── tier.py            # Knowledge graph and code search
```

## OpenClaw Integration

The Memory MCP server can be shared with OpenClaw for multi-channel access. When configured, preferences and context are shared across Claude Code CLI, WhatsApp, Telegram, Discord, and other channels.

### memory-mcp-bridge

OpenClaw's `memory-mcp-bridge` extension connects to this server:

**~/.openclaw/openclaw.json:**
```json
{
  "plugins": {
    "memory-mcp-bridge": {
      "enabled": true,
      "mcpCommand": "~/.claude-code-pp/bin/memory-mcp",
      "autoRecall": true,
      "autoCapture": true,
      "recallLimit": 5,
      "recallMinScore": 0.3
    }
  }
}
```

**Features:**
- **Auto-Recall**: Relevant memories injected before each message
- **Auto-Capture**: Important info stored after conversations
- **Category mapping**: OpenClaw categories mapped to Memory MCP types:
  - `preference` → `preference`
  - `decision` → `decision`
  - `entity` → `reference`
  - `fact` → `reference`
  - `other` → `note`

**Installation:**
```bash
# Via unified installer (recommended)
cd Claude-CodePlusPlus
./install.sh  # Select OpenClaw option

# Or manually
npm install -g openclaw@latest
openclaw onboard
```

## MCP Integration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_mcp.server"],
      "env": {
        "REDIS_URL": "redis://localhost:6379",
        "MEMORY_SQLITE_PATH": "~/.claude-code-pp/memory/memories.db",
        "NEO4J_URI": "bolt://localhost:7687",
        "LIVEGREP_URL": "http://localhost:8910"
      }
    }
  }
}
```

## Troubleshooting

### Redis connection refused
```bash
# Check if Redis is running
redis-cli ping

# Start Redis via Docker
docker run -d -p 6379:6379 redis:alpine
```

### Graphiti/Neo4j connection failed
```bash
# Check Neo4j
curl -u neo4j:password http://localhost:7474/db/neo4j/tx

# Start Neo4j via Docker
docker run -d -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5
```

### livegrep not responding
```bash
# Check livegrep server
curl http://localhost:8910/api/v1/search -d '{"query":"test"}'

# Verify index exists
ls -la /path/to/livegrep/index
```

### Embedding errors
```bash
# Check Ollama
curl http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test"}'

# Check OpenAI key
echo $OPENAI_API_KEY
```

### Test MCP connection
```bash
# Send test request
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m memory_mcp.server
```

### Async timeout errors
The system uses configurable timeouts (default 30s) for async operations. If you see timeout errors:
- Check network connectivity to external services
- Increase timeout in `async_utils.py` if needed
- Verify service health with `memory_stats` tool
