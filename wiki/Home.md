# Claude Code++

**An AI-native development environment that extends Claude Code with persistent memory, system control, multi-channel AI gateway, and intelligent model routing.**

Claude Code++ transforms Claude from a stateless assistant into a context-aware development partner that remembers your preferences, project decisions, and working patterns across sessions - whether you're in the terminal, on WhatsApp, or dictating to your whiteboard.

## Quick Navigation

### Getting Started
- [[Installation]] - Set up Claude Code++ on your system
- [[Quick-Start]] - Get running in 5 minutes
- [[Configuration]] - Customize your environment

### Core Components
- [[Architecture]] - System design and component overview
- [[Memory-MCP]] - The persistent memory system
  - [[Memory-MCP-Tools]] - Tool reference and examples
  - [[Memory-MCP-Behavioral-Guidelines]] - How Claude uses memory
  - [[Memory-Tiers]] - Understanding hot/warm/cold/archive storage
- [[System-Controller]] - macOS accessibility integration
- [[Research-Environment]] - Voice + webcam whiteboard research mode
- [[OpenClaw]] - Multi-channel AI gateway (WhatsApp, Telegram, Discord, etc.)
- [[Prompts-MCP]] - Role-based prompting with awesome-chatgpt-prompts

### Reference
- [[Troubleshooting]] - Common issues and solutions
- [[API-Reference]] - MCP tool schemas
- [[Development]] - Contributing and development setup

## Key Features

### Persistent Memory
Claude remembers your preferences, past decisions, and project context across conversations. No more repeating yourself.

```
User: "Use the same auth approach we discussed"
Claude: [searches memory, finds JWT decision from last week]
        "Got it - using JWT with refresh token rotation,
         same as we decided for the API gateway project."
```

### Multi-Channel Access (OpenClaw)
Access Claude with your memory from any device:

| Channel | Use Case |
|---------|----------|
| **Terminal** | Development, coding, file operations |
| **WhatsApp** | Quick questions on the go |
| **Telegram** | Team collaboration |
| **Discord** | Community support |
| **iMessage** | Apple ecosystem |
| **Signal** | Privacy-focused communication |

Memory is shared across all channels - a preference set in terminal is available in WhatsApp.

### Tiered Storage
Optimized for different access patterns with automatic promotion:

| Tier | Storage | Speed | Use Case |
|------|---------|-------|----------|
| Hot | Redis | <1ms | Current session |
| Warm | Graphiti/Neo4j | <50ms | Knowledge graph, relationships |
| Cold | SQLite/livegrep | <100ms | Full-text search, code search |
| Archive | Obsidian Vault | <200ms | Human-readable documentation |

**20 MCP Tools** available across core (10), research (5), and tier-specific (5) categories.

### Session Continuity
Pick up exactly where you left off:

```
User: "Continue from yesterday"
Claude: [restores session state]
        "Resuming - we were implementing the rate limiter.
         You had decided on token bucket algorithm.
         Next up: Redis integration for distributed limiting."
```

### Research Environment
Hands-free research with voice and whiteboard:

```bash
start_research  # Launch voice + webcam mode
```

- Voice conversations with Claude
- Show diagrams, whiteboards, or documents
- Auto-stored in memory for future reference

### Role-Based Prompting
Adopt specialized personas on demand via the prompts MCP server.

## Quick Install

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
./install.sh
```

The unified installer handles everything:
- Memory MCP server setup
- Docker services (Redis, Neo4j)
- OpenClaw multi-channel gateway (optional)
- Research environment (optional)

**Total time: ~5 minutes**

## Requirements

- macOS 12+ (for System Controller)
- Python 3.10+
- Node.js 22+ (for OpenClaw)
- Docker (for Redis, Neo4j)

## Support

- [GitHub Issues](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/issues)
- Full documentation in this wiki
