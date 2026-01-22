# Architecture

Claude Code++ extends Claude Code with a modular architecture designed for persistent memory and system control.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code CLI                           │
│                    (Anthropic's official CLI)                    │
├─────────────────────────────────────────────────────────────────┤
│                         MCP Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Memory MCP  │  │ System Ctrl  │  │  External MCPs       │  │
│  │   (Python)   │  │   (Swift)    │  │  (filesystem, git)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      Storage Layer                               │
│  ┌────────┐ ┌─────────┐ ┌────────┐ ┌─────────┐ ┌───────────┐  │
│  │ Redis  │ │Graphiti │ │LanceDB │ │ SQLite  │ │  Vault    │  │
│  │  Hot   │ │  Warm   │ │  Warm  │ │  Cold   │ │ Archive   │  │
│  └────────┘ └─────────┘ └────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### MCP (Model Context Protocol)

Claude Code uses MCP to extend its capabilities through external servers. Each MCP server exposes tools that Claude can call.

```
Claude Code  ──JSON-RPC──▶  MCP Server  ──▶  Backend Storage
   │                            │
   │  tools/list               │  Initialize
   │  tools/call               │  Execute
   │◀──────────────────────────│  Return result
```

### Memory MCP Server

The Memory MCP server provides persistent context management:

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory MCP Server                         │
├─────────────────────────────────────────────────────────────┤
│  Tool Handlers                                               │
│  ├── memory_store    → Write to appropriate tier            │
│  ├── memory_search   → Query across all tiers               │
│  ├── memory_recall   → Retrieve by ID                       │
│  ├── memory_delete   → Remove from all tiers                │
│  ├── memory_list     → List with filters                    │
│  ├── session_save    → Persist session state                │
│  ├── session_restore → Load session state                   │
│  ├── vault_write     → Write to Obsidian vault              │
│  ├── vault_read      → Read from Obsidian vault             │
│  └── memory_stats    → Health and statistics                │
├─────────────────────────────────────────────────────────────┤
│  Tier Manager                                                │
│  ├── Automatic promotion (cold → warm → hot)                │
│  ├── Automatic demotion (hot → warm → cold)                 │
│  └── Access pattern tracking                                │
├─────────────────────────────────────────────────────────────┤
│  Storage Backends                                            │
│  ├── RedisClient      (optional)                            │
│  ├── GraphitiClient   (optional)                            │
│  ├── LanceDBClient    (optional)                            │
│  ├── SQLiteIndex      (required)                            │
│  ├── LivegrepClient   (optional)                            │
│  └── VaultManager     (required)                            │
└─────────────────────────────────────────────────────────────┘
```

## Memory Tier Architecture

### Tier Characteristics

| Tier | Storage | Latency | Capacity | Persistence | Use Case |
|------|---------|---------|----------|-------------|----------|
| Hot | Redis | <1ms | ~1000 items | Session | Active working context |
| Warm | Graphiti | <50ms | Unlimited | Permanent | Entity relationships |
| Warm | LanceDB | <10ms | 100k+ vectors | Permanent | Semantic similarity |
| Cold | SQLite | <50ms | Unlimited | Permanent | Metadata, full-text |
| Cold | livegrep | <100ms | All repos | Index | Code search |
| Archive | Vault | <200ms | Unlimited | Permanent | Human-readable docs |

### Data Flow

```
Store Operation:
  Content → Validate → SQLite (metadata) → Appropriate tier(s)
                                ↓
                    [If important] → Vault (archive)
                    [If entity/fact] → Graphiti
                    [If embeddings] → LanceDB

Search Operation:
  Query → Determine type → Route to tier(s) → Merge results → Return
            │
            ├── Relationships? → Graphiti
            ├── Semantic? → LanceDB
            ├── Code? → livegrep
            ├── Exact match? → SQLite FTS
            └── Session context? → Redis
```

### Tier Promotion/Demotion

Access patterns drive automatic tier management:

```
                    Access Frequency
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    ▼                     │                     ▼
┌────────┐           ┌────────┐           ┌────────┐
│  Hot   │◀─promote──│  Warm  │◀─promote──│  Cold  │
│ Redis  │──demote─▶ │Graphiti│──demote─▶ │ SQLite │
└────────┘           │LanceDB │           └────────┘
                     └────────┘
```

Promotion criteria:
- Accessed >3 times in current session → promote to hot
- Accessed >5 times total → promote to warm

Demotion criteria:
- Not accessed in 24h → demote from hot
- Not accessed in 7d → demote from warm

## Document Schema

All memories share a common schema:

```python
@dataclass
class MemoryDocument:
    id: str                    # Unique identifier
    content: str               # The actual content
    doc_type: str              # code, note, conversation, reference
    source: str                # Origin (file path, URL, conversation ID)
    tags: List[str]            # Categorization tags
    project: Optional[str]     # Project association
    importance: float          # 0.0 to 1.0
    created_at: datetime       # Creation timestamp
    updated_at: datetime       # Last update timestamp
    accessed_at: datetime      # Last access timestamp
    access_count: int          # Total access count
    embedding: Optional[List[float]]  # Vector embedding
    metadata: Dict[str, Any]   # Additional metadata
```

## Session Management

Sessions capture working state for continuity:

```python
@dataclass
class SessionState:
    session_id: str
    project_path: str
    active_files: List[str]    # Files being worked on
    recent_memories: List[str] # Recently accessed memory IDs
    context: Dict[str, Any]    # Custom context (tasks, decisions)
    created_at: datetime
    updated_at: datetime
```

Session lifecycle:
1. **Start**: `session_restore` loads previous state
2. **During**: Automatic tracking of accessed memories
3. **End**: `session_save` persists current state

## Graceful Degradation

The system operates with reduced functionality when optional components are unavailable:

| Missing Component | Impact | Fallback |
|-------------------|--------|----------|
| Redis | No hot cache | Direct SQLite queries (slower) |
| LanceDB | No semantic search | Text-based search only |
| Graphiti | No relationship queries | Tag-based filtering |
| livegrep | No cross-repo code search | Local grep |
| Embeddings | No vector similarity | Keyword matching |

Core components (SQLite + Vault) are always required.

## Security Model

### Data Storage
- All data stored locally (no cloud sync by default)
- SQLite database in `~/.claude-code-pp/memory/`
- Vault files in `~/.claude-code-pp/memory/vault/`

### Access Control
- MCP servers run with user permissions
- No network access required (except optional services)
- Redis can be configured with authentication

### Sensitive Data
- Passwords/tokens should NOT be stored in memory
- PII handling is user's responsibility
- Vault files can be gitignored for privacy

## Extension Points

### Custom Embedding Providers
Implement `EmbeddingProvider` interface to add new providers.

### Custom Storage Backends
Implement storage interface to add new tiers.

### Hooks Integration
Claude Code hooks can trigger memory operations:
- PreToolUse: Remind to search memory
- PostToolUse: Suggest storing results
- Stop: Prompt session save

## Related Pages

- [[Memory-MCP]] - Detailed Memory MCP documentation
- [[Memory-Tiers]] - Deep dive on tier architecture
- [[Configuration]] - Customizing the architecture
