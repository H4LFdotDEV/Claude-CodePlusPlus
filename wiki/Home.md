# Claude Code++

**An AI-native development environment that extends Claude Code with persistent memory, system control, and intelligent model routing.**

Claude Code++ transforms Claude from a stateless assistant into a context-aware development partner that remembers your preferences, project decisions, and working patterns across sessions.

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

### Tiered Storage
Optimized for different access patterns:

| Tier | Storage | Speed | Use Case |
|------|---------|-------|----------|
| Hot | Redis | <1ms | Current session |
| Warm | Graphiti/LanceDB | <50ms | Knowledge graph, semantic search |
| Cold | SQLite/livegrep | <100ms | Full-text search, code search |
| Archive | Obsidian Vault | <200ms | Human-readable documentation |

### Session Continuity
Pick up exactly where you left off:

```
User: "Continue from yesterday"
Claude: [restores session state]
        "Resuming - we were implementing the rate limiter.
         You had decided on token bucket algorithm.
         Next up: Redis integration for distributed limiting."
```

### Role-Based Prompting
Adopt specialized personas on demand via the prompts MCP server.

## Requirements

- macOS 12+ (for System Controller)
- Python 3.10+
- Redis (optional, for hot cache)
- Neo4j (optional, for Graphiti knowledge graph)

## Support

- [GitHub Issues](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/issues)
- Full documentation in this wiki
