# Claude Code++

An AI-native development environment that extends Claude Code with persistent memory, system control, and intelligent model routing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                         │
├─────────────────────────────────────────────────────────────┤
│  MCP Servers                                                 │
│  ├── Memory MCP (Python) - Tiered memory system             │
│  ├── System Controller (Swift) - macOS Accessibility API    │
│  └── External MCPs (filesystem, git, browser, etc.)         │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                              │
│  ├── Redis - Hot memory cache (port 6379)                   │
│  ├── ChromaDB - Vector embeddings (port 8000)               │
│  └── LiteLLM - Model routing (port 4000)                    │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and install
git clone <repo> claude-code-pp
cd claude-code-pp
./install.sh

# Start infrastructure
docker-compose -f docker/docker-compose.yaml up -d

# Verify installation
claude --mcp-debug
```

## Components

### Memory MCP Server (Python)

Tiered memory system with automatic promotion/demotion:

| Tier | Storage | Access Time | Capacity | Use Case |
|------|---------|-------------|----------|----------|
| Hot | Redis | <1ms | 1000 items | Active session cache |
| Warm | Graphiti | <50ms | Relationship-based | Knowledge graph (entities, facts) |
| Warm | LanceDB | <10ms | 100k+ vectors | Semantic similarity search |
| Cold | SQLite | <50ms | Unlimited | Metadata, full-text search |
| Cold | livegrep | <100ms | All repos | Cross-repository code search |
| Archive | Obsidian | <200ms | Unlimited | Human-readable notes |

**MCP Tools:**
- `memory_store` - Store content with type, tags, importance
- `memory_search` - Semantic search across all tiers
- `memory_recall` - Retrieve by ID or pattern
- `memory_delete` - Remove memories
- `memory_list` - List memories by type/tag
- `session_save` - Persist current session
- `session_restore` - Load previous session
- `vault_write` - Write to Obsidian vault
- `vault_read` - Read from Obsidian vault
- `memory_stats` - Get memory statistics

### System Controller (Swift)

macOS Accessibility API integration for screen reading and system control.

**MCP Methods:**
- `click`, `double_click` - Mouse actions
- `scroll` - Scroll at coordinates
- `type_text` - Type text with optional modifiers
- `hotkey` - Press keyboard shortcuts
- `clipboard_get`, `clipboard_set` - Clipboard access
- `focus_app` - Focus application by name
- `move_window`, `resize_window` - Window management
- `screen_read_at` - Read text at coordinates
- `get_active_window` - Get current window info
- `check_accessibility` - Verify permissions

**Permission Levels:**
| Level | Name | Capabilities |
|-------|------|--------------|
| 0 | Sandboxed | Read-only screen access |
| 1 | Observer | Screen reading, clipboard read |
| 2 | Basic | Mouse click, basic keyboard |
| 3 | Standard | Full keyboard, clipboard write |
| 4 | Elevated | Window management, app focus |
| 5 | Unrestricted | All capabilities |

### LiteLLM Router

Intelligent model routing with cost optimization.

**Configured Models:**
- `claude-opus-4-5-20251101` - Complex reasoning
- `claude-sonnet-4-5-20251101` - Main development
- `gpt-4o` - Fallback/comparison
- `ollama/llama3.2` - Local inference

## Configuration

### Directory Structure

```
~/.claude-code-pp/
├── config/
│   ├── settings.yaml      # Main configuration
│   ├── mcp-servers.json   # MCP server definitions
│   └── litellm.yaml       # Model routing config
├── memory/
│   ├── sqlite/            # Metadata and FTS
│   ├── lancedb/           # Vector embeddings
│   └── vault/             # Obsidian-compatible notes
├── logs/
└── cache/
```

### Environment Variables

```bash
# Required for full functionality
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional
VOYAGE_API_KEY=...          # Better embeddings
OBSIDIAN_VAULT_PATH=...     # Obsidian integration
REDIS_URL=redis://localhost:6379
```

### MCP Server Configuration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_mcp.server"],
      "env": {
        "REDIS_URL": "redis://localhost:6379",
        "SQLITE_PATH": "~/.claude-code-pp/memory/sqlite/memories.db"
      }
    },
    "system-controller": {
      "command": "system-controller-cli",
      "args": ["--stdio"]
    }
  }
}
```

## Docker Services

```bash
# Start all services
docker-compose -f docker/docker-compose.yaml up -d

# Start with optional profiles
docker-compose -f docker/docker-compose.yaml --profile browser up -d
docker-compose -f docker/docker-compose.yaml --profile local-llm up -d
```

**Services:**
| Service | Port | Purpose |
|---------|------|---------|
| redis | 6379 | Hot memory cache |
| chromadb | 8000 | Vector embeddings |
| litellm | 4000 | Model routing |
| playwright | 9222 | Browser automation (optional) |
| ollama | 11434 | Local LLM (optional) |

## Troubleshooting

### Memory MCP not connecting
```bash
# Check Redis
redis-cli ping

# Check MCP server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m memory_mcp.server
```

### System Controller permissions
```bash
# Check accessibility permissions
system-controller-cli --check-permissions

# Grant in System Preferences > Privacy > Accessibility
```

### Docker services not starting
```bash
# Check logs
docker-compose -f docker/docker-compose.yaml logs

# Restart specific service
docker-compose -f docker/docker-compose.yaml restart redis
```

### LiteLLM routing errors
```bash
# Test endpoint
curl http://localhost:4000/health

# Check configured models
curl http://localhost:4000/v1/models
```

## Development

### Building Swift Controller
```bash
cd swift-system-controller
swift build
swift test
```

### Running Python Tests
```bash
cd python
pip install -e ".[dev]"
pytest --cov=memory_mcp
```

### Project Structure
```
claude-code-pp/
├── swift-system-controller/   # macOS system control
├── python/                    # Memory MCP server
├── docker/                    # Docker configurations
├── config/                    # Configuration templates
├── .claude/                   # Claude Code extensions
│   ├── agents/               # Custom agents
│   ├── commands/             # Slash commands
│   ├── rules/                # Context rules
│   └── skills/               # Complex workflows
└── Archive/                   # Reference documentation
```

## Memory MCP Integration

### Automatic Behaviors

Memory behavioral guidelines are automatically loaded via `.claude/rules/memory-behavior.md`. Key behaviors:

- **Search-first principle**: Always search memory before answering context-dependent questions
- **Active memory management**: Store preferences, decisions, solutions; delete outdated info
- **Session lifecycle**: Restore at start, save at end, persist important context

### Hooks

Memory-related hooks in `.claude/hooks.json`:

| Hook | Trigger | Purpose |
|------|---------|---------|
| Memory reminder | Session end (Stop) | Reminds to save session and store learnings |
| Continue prompt | Session end (Stop) | Shows how to resume from memory |

### Role-Based Prompting (awesome-chatgpt-prompts)

The prompts MCP server (`prompts.chat`) provides access to a library of role-based prompts:

```
# List available prompts
mcp__prompts__list_prompts()

# Get a specific prompt
mcp__prompts__get_prompt(name: "Linux Terminal")

# Search prompts
mcp__prompts__search_prompts(query: "developer")
```

Useful for adopting specific personas (code reviewer, architect, debugger, etc.).

### Full Documentation

- Behavioral guidelines: `python/memory_mcp/SYSTEM_PROMPT.md`
- Tool schemas: `python/memory_mcp/tool_schemas.py`
- Tool examples: `python/memory_mcp/tool_examples.py`
