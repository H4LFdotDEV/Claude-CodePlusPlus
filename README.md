# Claude Code++

An AI-native development environment that extends Claude Code with persistent memory, intelligent search, and system control.

## Overview

Claude Code++ adds enterprise-grade capabilities to Claude Code through MCP (Model Context Protocol) servers:

- **Memory MCP** - Four-tier persistent memory (Redis → Graphiti → livegrep → Obsidian)
- **Search MCP** - Multi-layer search (Hound → livegrep → Graphiti → Semantic)
- **System Controller** - macOS Accessibility API integration
- **Infrastructure** - Docker-based services for Redis, Neo4j, and model routing

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE++                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  MEMORY SYSTEM (What Claude Knows)                                           │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐          │
│  │  Redis   │  │ Graphiti  │  │ livegrep  │  │  Obsidian Vault   │          │
│  │  (Hot)   │→ │  (Warm)   │→ │  (Cold)   │→ │  (Archive)        │          │
│  │ Session  │  │ Knowledge │  │ All-time  │  │  Human-readable   │          │
│  │ context  │  │ graph     │  │ artifacts │  │  export           │          │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘          │
│                                                                               │
│  SEARCH SYSTEM (How Claude Finds Things)                                     │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐          │
│  │  Hound   │  │ livegrep  │  │ Graphiti  │  │  Nomic + LanceDB  │          │
│  │ Project  │  │ Global    │  │ Graph     │  │  Semantic         │          │
│  │ regex    │  │ regex     │  │ traversal │  │  intent search    │          │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘          │
│                                                                               │
│  INFRASTRUCTURE                                                               │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐          │
│  │  Redis   │  │  Neo4j    │  │  SQLite   │  │  LiteLLM Router   │          │
│  │  Cache   │  │  Graph DB │  │  Metadata │  │  Model routing    │          │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Memory Tiers

| Tier | Technology | Purpose | Access Time |
|------|------------|---------|-------------|
| **Hot** | Redis | Session state, working context | <1ms |
| **Warm** | Graphiti/Neo4j | Knowledge graph (entities, relationships, temporal facts) | <10ms |
| **Cold** | livegrep | All historical code and artifacts | <50ms |
| **Archive** | Obsidian Vault | Human-readable markdown export | <100ms |

**Note:** SQLite stores metadata only (timestamps, tags, indexes) - not a primary storage tier.

## Search Layers

| Layer | Technology | Scope | Use Case |
|-------|------------|-------|----------|
| **Project** | Hound | Current project | Fast local regex search |
| **Global** | livegrep | All projects, all time | Cross-project pattern matching |
| **Graph** | Graphiti | Relationship traversal | "What uses this?" queries |
| **Semantic** | Nomic Embed + LanceDB | Intent-based | "Find authentication code" |

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
        "REDIS_URL": "redis://localhost:6379",
        "NEO4J_URI": "bolt://localhost:7687"
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
| `memory_recall` | Retrieve relevant context by ID or pattern |
| `memory_delete` | Remove memories (privacy deletion) |
| `memory_list` | List memories by type/tag/project |
| `memory_stats` | Get memory statistics across all tiers |

### Knowledge Graph (via Graphiti)

| Tool | Description |
|------|-------------|
| `get_entity` | Knowledge graph entity lookup |
| `trace_relationship` | Graph traversal queries |
| `get_timeline` | Temporal queries ("what changed last week?") |

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

## Project Structure

```
Claude-CodePlusPlus/
├── python/                    # Memory MCP Server
│   ├── memory_mcp/           # Core modules
│   │   ├── server.py         # MCP server implementation
│   │   ├── redis_client.py   # Hot tier (Redis)
│   │   ├── graphiti_manager.py # Warm tier (knowledge graph)
│   │   ├── livegrep_client.py  # Cold tier (artifact search)
│   │   ├── sqlite_index.py   # Metadata storage
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

# Memory System
REDIS_URL=redis://localhost:6379
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=...

# Optional
OPENAI_API_KEY=sk-...          # For Graphiti entity extraction
LIVEGREP_ENDPOINT=http://localhost:8910
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
```

| Service | Port | Purpose |
|---------|------|---------|
| redis | 6379 | Hot memory cache |
| neo4j | 7687 | Knowledge graph (Graphiti) |
| litellm | 4000 | Model routing |

## Roadmap

- [ ] Hound integration for project-local search
- [ ] Semantic search layer (Nomic Embed + LanceDB)
- [ ] Search MCP server (separate from Memory MCP)
- [ ] Windows/Linux System Controller

## License

Apache 2.0 - See [LICENSE.md](LICENSE.md)

## Contributing

Contributions welcome! Please read the contributing guidelines before submitting PRs.

## Acknowledgments

Built to extend [Claude Code](https://claude.ai/code) by Anthropic.
