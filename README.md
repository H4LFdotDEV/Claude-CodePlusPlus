# Claude Code++

An AI-native development environment that extends Claude Code with persistent memory, system control, and intelligent model routing.

## Overview

Claude Code++ adds enterprise-grade capabilities to Claude Code through MCP (Model Context Protocol) servers:

- **Memory MCP** - Four-tier persistent memory system (Redis → FAISS → SQLite → Obsidian)
- **System Controller** - macOS Accessibility API integration for screen reading and system control
- **Infrastructure** - Docker-based services for Redis, vector embeddings, and model routing

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
│  ├── Neo4j - Knowledge graph (port 7687)                    │
│  └── LiteLLM - Model routing (port 4000)                    │
└─────────────────────────────────────────────────────────────┘
```

## Memory Tiers

| Tier | Storage | Access Time | Capacity | Use Case |
|------|---------|-------------|----------|----------|
| Hot | Redis | <1ms | 1000 items | Active session context |
| Warm | FAISS + Graphiti | <10ms | 100k vectors | Recent context, knowledge graph |
| Cold | SQLite + livegrep | <50ms | Unlimited | Long-term storage, code search |
| Archive | Obsidian Vault | <100ms | Unlimited | Human-readable notes |

## Quick Start

### Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed
- Docker and Docker Compose
- Python 3.11+
- macOS (for System Controller)

### Installation

```bash
# Clone the repository
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus

# Start infrastructure services
docker-compose -f docker/docker-compose.yaml up -d

# Install Memory MCP
cd python
pip install -e .

# Configure Claude Code to use MCP servers
# Add to ~/.claude.json (see Configuration section)
```

### Configuration

Add to your `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_mcp.server"],
      "env": {
        "REDIS_URL": "redis://localhost:6379"
      }
    }
  }
}
```

## MCP Tools

### Memory Operations

| Tool | Description |
|------|-------------|
| `memory_store` | Store content with type, tags, and importance |
| `memory_search` | Semantic search across all tiers |
| `memory_recall` | Retrieve by ID |
| `memory_delete` | Remove memories |
| `memory_list` | List memories by type/tag/project |

### Session Management

| Tool | Description |
|------|-------------|
| `session_save` | Persist current session state |
| `session_restore` | Load previous session |

### Vault Operations

| Tool | Description |
|------|-------------|
| `vault_write` | Write to Obsidian vault |
| `vault_read` | Read from Obsidian vault |

### System Info

| Tool | Description |
|------|-------------|
| `memory_stats` | Get memory statistics across all tiers |

## Project Structure

```
Claude-CodePlusPlus/
├── python/                    # Memory MCP Server
│   ├── memory_mcp/           # Core modules
│   │   ├── server.py         # MCP server implementation
│   │   ├── redis_client.py   # Hot tier (Redis)
│   │   ├── faiss_manager.py  # Warm tier (vector search)
│   │   ├── graphiti_manager.py # Knowledge graph
│   │   ├── sqlite_index.py   # Cold tier (metadata)
│   │   └── vault_manager.py  # Archive tier (Obsidian)
│   └── tests/                # Test suite (750+ tests)
├── swift-system-controller/   # macOS System Controller
├── docker/                    # Docker Compose configs
├── config/                    # Configuration templates
└── bruno/                     # API testing collection
```

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
OPENAI_API_KEY=sk-...          # For OpenAI embeddings
VOYAGE_API_KEY=...             # For Voyage embeddings
NEO4J_PASSWORD=...             # For knowledge graph
REDIS_URL=redis://localhost:6379
```

## Development

### Running Tests

```bash
cd python
pip install -e ".[dev]"
pytest --cov=memory_mcp
```

### Building Swift Controller

```bash
cd swift-system-controller
swift build
swift test
```

## Docker Services

```bash
# Start all services
docker-compose -f docker/docker-compose.yaml up -d

# Check status
docker-compose -f docker/docker-compose.yaml ps

# View logs
docker-compose -f docker/docker-compose.yaml logs -f
```

| Service | Port | Purpose |
|---------|------|---------|
| redis | 6379 | Hot memory cache |
| neo4j | 7687 | Knowledge graph |
| litellm | 4000 | Model routing |

## License

Apache 2.0 - See [LICENSE.md](LICENSE.md)

## Contributing

Contributions welcome! Please read the contributing guidelines before submitting PRs.

## Acknowledgments

Built to extend [Claude Code](https://claude.ai/code) by Anthropic.
