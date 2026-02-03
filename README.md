# Claude Code++

An AI-native development environment that extends Claude Code with persistent memory, intelligent search, system control, and multi-channel AI gateway access.

## Overview

Claude Code++ transforms Claude from a stateless assistant into a context-aware development partner. It provides:

- **Memory MCP** - Four-tier persistent memory (Redis → Graphiti → SQLite → Obsidian)
- **Search MCP** - Multi-layer search (SQLite FTS → livegrep → Graphiti)
- **System Controller** - macOS Accessibility API integration
- **Research Environment** - Voice conversations + webcam whiteboard capture
- **OpenClaw Integration** - Multi-channel AI gateway (WhatsApp, Telegram, Discord, Slack, iMessage, Signal)
- **Infrastructure** - Docker-based services for Redis, Neo4j, and more

## Quick Start

### One-Liner Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/quick-install.sh | bash
```

For a fully automated install with defaults:

```bash
curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/quick-install.sh | bash -s -- --quick
```

### Manual Install

```bash
# Clone and install
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
./install.sh                  # Interactive
./install.sh --quick          # Use all defaults
./install.sh --with-openclaw  # Include OpenClaw
```

The installer will:
1. Detect your system resources and recommend an installation profile
2. Set up the Memory MCP server with tiered storage
3. Start Docker services (Redis, Neo4j)
4. Configure Claude Code to use the MCP servers
5. Optionally install OpenClaw for multi-channel access
6. Optionally set up the research environment (voice + webcam)

**Total install time: ~5 minutes** (excluding Docker image pulls)

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE++                                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CLIENTS                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Claude Code    │  │    OpenClaw     │  │      Research Environment       │   │
│  │     CLI         │  │  Multi-Channel  │  │    Voice + Webcam Whiteboard    │   │
│  │                 │  │  Gateway        │  │                                 │   │
│  │  Development    │  │  WhatsApp       │  │    Hands-free research with     │   │
│  │  terminal       │  │  Telegram       │  │    whiteboard capture           │   │
│  │                 │  │  Discord, etc.  │  │                                 │   │
│  └────────┬────────┘  └────────┬────────┘  └─────────────┬───────────────────┘   │
│           │                    │                         │                       │
│           └────────────────────┼─────────────────────────┘                       │
│                                │                                                 │
│                    ┌───────────▼───────────┐                                     │
│                    │    SHARED MEMORY      │                                     │
│                    │    (Memory MCP)       │                                     │
│                    └───────────┬───────────┘                                     │
│                                │                                                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│  MEMORY TIERS (Shared across all clients)                                        │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐               │
│  │  Redis   │  │ Graphiti  │  │  SQLite   │  │  Obsidian Vault   │               │
│  │  (Hot)   │→ │  (Warm)   │→ │  (Cold)   │→ │  (Archive)        │               │
│  │ Session  │  │ Knowledge │  │ Full-text │  │  Human-readable   │               │
│  │ context  │  │ graph     │  │ search    │  │  export           │               │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘               │
│                                                                                  │
│  SEARCH SYSTEM                                                                   │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐               │
│  │  SQLite  │  │ livegrep  │  │ Graphiti  │  │    Semantic       │               │
│  │ Full-text│  │ Global    │  │ Graph     │  │    (planned)      │               │
│  │ search   │  │ regex     │  │ traversal │  │                   │               │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘               │
│                                                                                  │
│  INFRASTRUCTURE (Docker)                                                         │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐               │
│  │  Redis   │  │  Neo4j    │  │ Playwright│  │     OpenClaw      │               │
│  │  Cache   │  │  Graph DB │  │  Browser  │  │     Gateway       │               │
│  │  :6379   │  │  :7474    │  │  :9222    │  │     :18789        │               │
│  └──────────┘  └───────────┘  └───────────┘  └───────────────────┘               │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Memory Tiers

| Tier | Technology | Purpose | Access Time |
|------|------------|---------|-------------|
| **Hot** | Redis | Session state, working context | <1ms |
| **Warm** | Graphiti/Neo4j | Knowledge graph (entities, relationships) | <10ms |
| **Cold** | SQLite/livegrep | Full-text search, code search | <50ms |
| **Archive** | Obsidian Vault | Human-readable markdown export | <100ms |

**Key Feature:** All memory is shared across Claude Code CLI and OpenClaw channels. A preference learned in a terminal session is instantly available in WhatsApp.

## OpenClaw Integration

OpenClaw provides multi-channel AI gateway access to Claude with shared memory:

| Channel | Description |
|---------|-------------|
| WhatsApp | Chat via Baileys web or Twilio |
| Telegram | Full bot integration |
| Discord | Server and DM support |
| Slack | Workspace integration |
| iMessage | macOS native (via BlueBubbles) |
| Signal | Privacy-focused messaging |
| Matrix | Decentralized chat |

**Memory Bridge:** The `memory-mcp-bridge` extension connects OpenClaw to the same Memory MCP server, enabling:

```
Terminal: "I prefer tabs over spaces"
   ↓
Claude Code++ stores preference
   ↓
WhatsApp: "How should I format this code?"
   ↓
OpenClaw: "I'll use tabs - that's your preference from our terminal session"
```

## MCP Tools

### Memory Operations (10 core tools)

| Tool | Description |
|------|-------------|
| `memory_store` | Store content with type, tags, and importance |
| `memory_search` | Multi-tier search with automatic routing |
| `memory_recall` | Retrieve by ID (tracks access for promotion) |
| `memory_delete` | Remove memories (GDPR deletion) |
| `memory_list` | List memories by type/tag/project |
| `session_save` | Persist current session state |
| `session_restore` | Load previous session |
| `vault_write` | Write to Obsidian vault |
| `vault_read` | Read from Obsidian vault |
| `memory_stats` | Get memory statistics with tier health |

### Research Tools (5 tools)

| Tool | Description |
|------|-------------|
| `research_session_start` | Start voice/whiteboard session |
| `research_session_end` | End session with summary |
| `research_transcript_store` | Store voice transcripts |
| `research_capture_store` | Store whiteboard captures |
| `research_search` | Search research data |

### Tier-Specific Tools (5 tools)

| Tool | Description |
|------|-------------|
| `search_entities` | Search Graphiti for entities |
| `search_facts` | Search Graphiti for facts |
| `code_search` | RE2 regex via livegrep |
| `search_function` | Find function definitions |
| `search_class` | Find class definitions |

## Installation Profiles

The installer detects your system and recommends a profile:

| Profile | Components | Requirements |
|---------|------------|--------------|
| **minimal** | SQLite + Vault | Python 3.10+ |
| **standard** | + Redis | + Docker |
| **full** | + Neo4j/Graphiti | 4GB+ RAM |
| **enterprise** | + livegrep | 8GB+ RAM |

## Docker Services

```bash
# Start core services
docker-compose -f docker/docker-compose.yaml up -d

# Start with OpenClaw
docker-compose -f docker/docker-compose.yaml --profile openclaw up -d

# Start with all optional services
docker-compose -f docker/docker-compose.yaml --profile livegrep --profile browser --profile openclaw up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| redis | 6379 | Hot memory cache |
| neo4j | 7474/7687 | Knowledge graph (Graphiti) |
| playwright | 9222 | Browser automation |
| openclaw | 18789 | Multi-channel gateway |
| openclaw-browser | 9223 | OpenClaw browser sandbox |

## Project Structure

```
Claude-CodePlusPlus/
├── python/                     # Memory MCP Server
│   └── memory_mcp/             # Core modules
├── swift-system-controller/    # macOS System Controller
├── openclaw/                   # Multi-channel gateway (submodule)
├── docker/                     # Docker Compose configs
├── config/                     # Configuration templates
├── wiki/                       # Documentation
├── .claude/                    # Claude Code extensions
│   ├── agents/                 # Custom agents
│   ├── commands/               # Slash commands
│   ├── rules/                  # Context rules
│   └── skills/                 # Complex workflows
└── CAIIDE++/                   # VS Code fork (optional)
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

# OpenClaw (optional)
TELEGRAM_BOT_TOKEN=...
DISCORD_BOT_TOKEN=...
```

## Verification

After installation, verify everything works:

```bash
# Check MCP servers
claude --mcp-debug

# In Claude Code, run:
memory_stats

# Check OpenClaw (if installed)
openclaw channels status
openclaw memory stats
```

## Roadmap

- [x] Four-tier memory system
- [x] OpenClaw multi-channel integration
- [x] Unified installer
- [ ] Semantic search layer
- [ ] Windows/Linux System Controller
- [ ] CAIIDE++ VS Code fork integration

## License

Apache 2.0 - See [LICENSE.md](LICENSE.md)

## Contributing

Contributions welcome! Please read the contributing guidelines before submitting PRs.

## Acknowledgments

Built to extend [Claude Code](https://claude.ai/code) by Anthropic.
