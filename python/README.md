# Memory MCP Server

Tiered memory system for Claude Code++ with Redis, FAISS, SQLite, and Obsidian vault integration.

## Installation

```bash
# Basic installation (SQLite + Obsidian only)
pip install -e .

# With Redis hot cache
pip install -e ".[redis]"

# With FAISS vector search
pip install -e ".[faiss]"

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
│                  (JSON-RPC 2.0 over stdio)                  │
├─────────────────────────────────────────────────────────────┤
│  Memory Tiers                                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐│
│  │  Redis  │→ │  FAISS  │→ │ SQLite  │→ │ Obsidian Vault  ││
│  │  (Hot)  │  │ (Warm)  │  │ (Cold)  │  │   (Archive)     ││
│  │  <1ms   │  │  <10ms  │  │  <50ms  │  │     <100ms      ││
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  Embedding Providers (with fallback)                         │
│  Local Ollama → OpenAI → Voyage AI                          │
└─────────────────────────────────────────────────────────────┘
```

### Tier Behavior

| Tier | Storage | Access Time | Capacity | Automatic |
|------|---------|-------------|----------|-----------|
| Hot | Redis | <1ms | 1000 items | Session cache |
| Warm | FAISS | <10ms | 100k vectors | Recent embeddings |
| Cold | SQLite | <50ms | Unlimited | All metadata |
| Archive | Obsidian | <100ms | Unlimited | Human-readable |

Components gracefully degrade if unavailable:
- No Redis → Skip hot cache
- No FAISS → Skip vector search (text search only)
- No embeddings → Skip semantic search

## MCP Tools

### memory_store
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

### memory_search
Search memory using text or semantic similarity.

```json
{
  "name": "memory_search",
  "arguments": {
    "query": "fibonacci algorithm",
    "type": "hybrid",
    "limit": 10,
    "filters": {
      "doc_type": "code",
      "project": "my-project"
    }
  }
}
```

**Parameters:**
- `query` (required): Search query
- `type` (optional): `text` | `semantic` | `hybrid` (default: hybrid)
- `limit` (optional): Max results (default: 10)
- `filters` (optional): Filter by doc_type, project, or tags

### memory_recall
Recall a specific memory by ID.

```json
{
  "name": "memory_recall",
  "arguments": {
    "id": "abc123def456"
  }
}
```

### memory_delete
Delete a memory by ID.

```json
{
  "name": "memory_delete",
  "arguments": {
    "id": "abc123def456"
  }
}
```

### memory_list
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

### session_save
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

### session_restore
Restore a previous session.

```json
{
  "name": "session_restore",
  "arguments": {
    "session_id": "uuid-of-session"
  }
}
```

### vault_write
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

**Parameters:**
- `path` (required): Note path (without .md extension)
- `content` (required): Markdown content
- `folder` (optional): `code` | `notes` | `conversations` | `references` | `daily`
- `tags` (optional): Array of tags

### vault_read
Read a note from the Obsidian vault.

```json
{
  "name": "vault_read",
  "arguments": {
    "path": "notes/project-notes/api-design"
  }
}
```

### memory_stats
Get memory system statistics.

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
  "faiss_count": 1200,
  "redis_keys": 45,
  "vault_notes": 89,
  "components": {
    "redis": true,
    "faiss": true,
    "embeddings": true
  }
}
```

## Configuration

### Environment Variables

```bash
# Storage paths
MEMORY_SQLITE_PATH=~/.claude-code-pp/memory/memories.db
MEMORY_FAISS_PATH=~/.claude-code-pp/memory/faiss/
OBSIDIAN_VAULT_PATH=~/Documents/ObsidianVault

# Redis
REDIS_URL=redis://localhost:6379

# Embedding providers (in order of preference)
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...
VOYAGE_API_KEY=pa-...
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
  faiss:
    path: ~/.claude-code-pp/memory/faiss/
    dimension: 1536
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
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=memory_mcp --cov-report=term-missing

# Run specific test file
pytest tests/test_server.py -v
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
├── server.py           # MCP protocol server
├── config.py           # Configuration management
├── sqlite_index.py     # SQLite storage layer
├── redis_client.py     # Redis hot cache
├── faiss_manager.py    # FAISS vector index
├── vault_manager.py    # Obsidian vault integration
├── embedding_provider.py  # Embedding providers
└── session_manager.py  # Session persistence
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
        "MEMORY_SQLITE_PATH": "~/.claude-code-pp/memory/memories.db"
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

### FAISS import error
```bash
# Install CPU version
pip install faiss-cpu

# Or GPU version (requires CUDA)
pip install faiss-gpu
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
