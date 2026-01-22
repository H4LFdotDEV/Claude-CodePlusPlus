# Configuration

Comprehensive guide to configuring Claude Code++.

## Configuration Hierarchy

Claude Code++ uses a layered configuration system:

```
1. Environment variables (highest priority)
2. ~/.claude.json (global MCP servers)
3. ~/.claude/settings.json (global settings)
4. Project CLAUDE.md (project instructions)
5. Project .claude/rules/*.md (project rules)
6. Project .claude/hooks.json (project hooks)
```

## MCP Server Configuration

### Location

MCP servers are configured in `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "/path/to/memory-mcp",
      "args": [],
      "env": {
        "REDIS_URL": "redis://localhost:6379"
      }
    },
    "prompts": {
      "command": "npx",
      "args": ["-y", "prompts.chat", "mcp"]
    }
  }
}
```

### Memory MCP Options

**Using pre-built binary:**
```json
{
  "memory": {
    "command": "~/.claude-code-pp/bin/memory-mcp",
    "args": []
  }
}
```

**Using Python directly:**
```json
{
  "memory": {
    "command": "python",
    "args": ["-m", "memory_mcp.server"],
    "env": {
      "PYTHONPATH": "/path/to/claude-code-pp/python"
    }
  }
}
```

**With environment variables:**
```json
{
  "memory": {
    "command": "~/.claude-code-pp/bin/memory-mcp",
    "args": [],
    "env": {
      "REDIS_URL": "redis://localhost:6379",
      "MEMORY_MCP_LOG_LEVEL": "DEBUG",
      "MEMORY_MCP_LOG_FILE": "~/.claude-code-pp/logs/memory.log"
    }
  }
}
```

## Environment Variables

### Memory MCP Server

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_MCP_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `MEMORY_MCP_LOG_FILE` | None | Log file path (stderr if not set) |
| `MEMORY_MCP_TRACE_ENABLED` | `true` | Enable request tracing |
| `MEMORY_MCP_TRACE_FILE` | None | Trace output file (JSON lines) |

### Storage Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLITE_PATH` | `~/.claude-code-pp/memory/sqlite/memories.db` | SQLite database path |
| `OBSIDIAN_VAULT_PATH` | `~/.claude-code-pp/memory/vault` | Vault directory |
| `LANCEDB_PATH` | `~/.claude-code-pp/memory/lancedb` | LanceDB directory |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `REDIS_PASSWORD` | None | Redis password |
| `REDIS_DB` | `0` | Redis database number |

### Graphiti (Neo4j)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Required | Neo4j password |
| `GRAPHITI_ENABLED` | `false` | Enable Graphiti integration |

### Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `local` | Provider: `local`, `openai`, `voyage` |
| `OPENAI_API_KEY` | None | OpenAI API key (for OpenAI embeddings) |
| `VOYAGE_API_KEY` | None | Voyage API key (for Voyage embeddings) |
| `EMBEDDING_MODEL` | Provider default | Specific model to use |

### livegrep

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVEGREP_ENABLED` | `false` | Enable livegrep integration |
| `LIVEGREP_URL` | `http://localhost:8910` | livegrep server URL |
| `LIVEGREP_INDEX_PATH` | None | Path to livegrep index |

## Directory Structure

Default directory layout:

```
~/.claude-code-pp/
├── bin/
│   └── memory-mcp          # Compiled MCP server
├── config/
│   ├── settings.yaml       # Main configuration
│   └── litellm.yaml        # Model routing (optional)
├── memory/
│   ├── sqlite/
│   │   └── memories.db     # SQLite database
│   ├── lancedb/            # Vector embeddings
│   └── vault/              # Obsidian-compatible notes
│       ├── code/
│       ├── notes/
│       ├── conversations/
│       ├── references/
│       └── daily/
├── logs/
│   └── memory.log          # Server logs
└── cache/
```

## Project Configuration

### CLAUDE.md

Project-specific instructions in `CLAUDE.md` at project root:

```markdown
# Project Name

## Project Context
This is an API gateway service using Node.js and TypeScript.

## Conventions
- Use async/await, not callbacks
- All functions should have JSDoc comments
- Tests required for all new features

## Key Files
- src/index.ts - Entry point
- src/middleware/ - Express middleware
- tests/ - Jest tests
```

### Rules Files

Add rules in `.claude/rules/` directory:

```
.claude/
└── rules/
    ├── coding-style.md      # Code style rules
    ├── testing.md           # Testing requirements
    ├── memory-behavior.md   # Memory usage guidelines
    └── security.md          # Security practices
```

Each rule file is automatically loaded.

### Hooks Configuration

Configure hooks in `.claude/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "tool == \"Bash\"",
        "hooks": [
          {
            "type": "command",
            "command": "#!/bin/bash\necho 'Pre-hook' >&2\ncat"
          }
        ],
        "description": "Pre-bash hook"
      }
    ],
    "PostToolUse": [],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "#!/bin/bash\necho '[Memory] Session ending' >&2\ncat"
          }
        ],
        "description": "Session end reminder"
      }
    ]
  }
}
```

### Hook Types

| Type | Trigger | Use Case |
|------|---------|----------|
| `PreToolUse` | Before tool execution | Validation, reminders |
| `PostToolUse` | After tool execution | Formatting, checks |
| `Stop` | Session end | Cleanup, reminders |

### Hook Matchers

```javascript
// Exact tool match
"tool == \"Bash\""

// Tool with condition
"tool == \"Bash\" && tool_input.command matches \"git push\""

// File type match
"tool == \"Edit\" && tool_input.file_path matches \"\\.ts$\""

// Any tool
"*"
```

## Vault Configuration

### Folder Structure

Configure vault folders for different content types:

| Folder | Content Type |
|--------|--------------|
| `code/` | Code snippets, implementations |
| `notes/` | General notes, observations |
| `conversations/` | Conversation logs |
| `references/` | Documentation, decisions |
| `daily/` | Daily notes |

### Frontmatter

Vault notes support YAML frontmatter:

```markdown
---
tags:
  - architecture
  - auth
project: api-gateway
created: 2024-01-15
---

# Authentication Architecture
...
```

## Performance Tuning

### Redis Configuration

For high-traffic usage, tune Redis:

```
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save ""  # Disable persistence for pure cache
```

### SQLite Optimization

SQLite is tuned by default, but for large databases:

```python
# Already configured in SQLiteIndex
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
```

### Embedding Cache

Cache embeddings to reduce API calls:

```bash
export EMBEDDING_CACHE_SIZE=10000
export EMBEDDING_CACHE_TTL=86400  # 24 hours
```

## Troubleshooting Configuration

### Verify MCP Servers

```bash
claude --mcp-debug
```

### Check Configuration Loading

```bash
# View effective configuration
cat ~/.claude.json | jq '.mcpServers'

# Check rules loading
ls -la /path/to/project/.claude/rules/
```

### Enable Debug Logging

```bash
export MEMORY_MCP_LOG_LEVEL=DEBUG
export MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/debug.log
```

## Related Pages

- [[Installation]] - Initial setup
- [[Architecture]] - System design
- [[Troubleshooting]] - Common issues
