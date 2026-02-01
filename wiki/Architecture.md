# Architecture

Claude Code++ extends Claude Code with a modular architecture designed for persistent memory, multi-channel access, and system control.

## System Overview

```
+-------------------------------------------------------------------------+
|                          CLAUDE CODE++                                   |
+-------------------------------------------------------------------------+
|                           Client Layer                                   |
|  +----------------+  +----------------+  +----------------------------+  |
|  |  Claude Code  |  |    OpenClaw   |  |   Research Environment    |  |
|  |     CLI       |  |  Multi-Channel |  |   Voice + Webcam          |  |
|  |  (Terminal)   |  |   Gateway      |  |   Whiteboard              |  |
|  +-------+-------+  +-------+--------+  +-------------+-------------+  |
|          |                  |                         |                 |
|          +------------------+---------+---------------+                 |
|                                       |                                 |
|                           +-----------v-----------+                     |
|                           |    Shared Memory      |                     |
|                           |    (Memory MCP)       |                     |
|                           +-----------+-----------+                     |
|                                       |                                 |
+-------------------------------------------------------------------------+
|                           MCP Layer                                      |
|  +----------------+  +----------------+  +----------------------------+  |
|  |  Memory MCP   |  | System Ctrl   |  |  External MCPs             |  |
|  |   (Python)    |  |   (Swift)     |  |  (filesystem, git, etc.)   |  |
|  +----------------+  +----------------+  +----------------------------+  |
+-------------------------------------------------------------------------+
|                         Storage Layer                                    |
|  +--------+ +-----------+ +--------+ +-----------+ +-----------------+  |
|  | Redis  | | Graphiti  | | SQLite | | livegrep  | |      Vault      |  |
|  |  Hot   | |   Warm    | |  Cold  | |   Cold    | |     Archive     |  |
|  +--------+ +-----------+ +--------+ +-----------+ +-----------------+  |
+-------------------------------------------------------------------------+
|                       Infrastructure                                     |
|  +--------+ +-----------+ +-----------+ +-----------------------------+ |
|  | Redis  | |  Neo4j    | | Playwright| |  OpenClaw Gateway           | |
|  | :6379  | |  :7474    | |  :9222    | |  :18789                     | |
|  +--------+ +-----------+ +-----------+ +-----------------------------+ |
+-------------------------------------------------------------------------+
```

## Component Architecture

### MCP (Model Context Protocol)

Claude Code uses MCP to extend its capabilities through external servers. Each MCP server exposes tools that Claude can call.

```
Claude Code  --JSON-RPC-->  MCP Server  -->  Backend Storage
   |                            |
   |  tools/list               |  Initialize
   |  tools/call               |  Execute
   |<--------------------------|  Return result
```

### Memory MCP Server

The Memory MCP server provides persistent context management with **20 tools** across three categories:

```
+---------------------------------------------------------------------+
|                    Memory MCP Server                                 |
+---------------------------------------------------------------------+
|  Handler Layer (6 handlers)                                          |
|  +------------------------------------------------------------------+
|  | MemoryHandler   | SessionHandler | VaultHandler                  |
|  | StatsHandler    | ResearchHandler | TierHandler                  |
|  +------------------------------------------------------------------+
+---------------------------------------------------------------------+
|  Core Tool Handlers (10 tools)                                       |
|  +-- memory_store    -> Write to appropriate tier                   |
|  +-- memory_search   -> Multi-tier search with TierManager          |
|  +-- memory_recall   -> Retrieve by ID (tracks access)              |
|  +-- memory_delete   -> Remove from all tiers                       |
|  +-- memory_list     -> List with filters                           |
|  +-- session_save    -> Persist session state                       |
|  +-- session_restore -> Load session state                          |
|  +-- vault_write     -> Write to Obsidian vault                     |
|  +-- vault_read      -> Read from Obsidian vault                    |
|  +-- memory_stats    -> Health, statistics, tier health             |
+---------------------------------------------------------------------+
|  Research Tool Handlers (5 tools)                                    |
|  +-- research_session_start  -> Start voice/whiteboard session      |
|  +-- research_session_end    -> End session with summary            |
|  +-- research_transcript_store -> Store voice transcripts           |
|  +-- research_capture_store  -> Store whiteboard captures           |
|  +-- research_search         -> Search research data                |
+---------------------------------------------------------------------+
|  Tier-Specific Tool Handlers (5 tools)                               |
|  +-- search_entities  -> Search Graphiti for entities               |
|  +-- search_facts     -> Search Graphiti for facts                  |
|  +-- code_search      -> RE2 regex via livegrep                     |
|  +-- search_function  -> Find function definitions                  |
|  +-- search_class     -> Find class/struct definitions              |
+---------------------------------------------------------------------+
|  Orchestration Layer                                                 |
|  +-- TierManager       (multi-tier search orchestration)            |
|  +-- AccessTracker     (LRU cache, max 10k entries)                 |
|  +-- run_async         (async/sync bridge with timeout)             |
+---------------------------------------------------------------------+
|  Storage Backends                                                    |
|  +-- RedisClient      (optional, hot tier)                          |
|  +-- GraphitiManager  (optional, warm tier)                         |
|  +-- SQLiteIndex      (required, cold tier)                         |
|  +-- LivegrepClient   (optional, cold tier)                         |
|  +-- VaultManager     (required, archive tier)                      |
+---------------------------------------------------------------------+
```

## Memory Tier Architecture

### Tier Characteristics

| Tier | Storage | Latency | Capacity | Persistence | Use Case |
|------|---------|---------|----------|-------------|----------|
| Hot | Redis | <1ms | ~1000 items | Session | Active working context |
| Warm | Graphiti/Neo4j | <50ms | Relationship-based | Permanent | Entity relationships |
| Cold | SQLite | <50ms | Unlimited | Permanent | Metadata, full-text |
| Cold | livegrep | <100ms | All repos | Index | Code search |
| Archive | Vault | <200ms | Unlimited | Permanent | Human-readable docs |

### Data Flow

```
Store Operation:
  Content -> Validate -> SQLite (metadata) -> Appropriate tier(s)
                                |
                    [If doc_type=code/note] -> Vault (archive)
                    [If promoted] -> Graphiti (warm)

Search Operation:
  Query -> TierManager -> Route to tier(s) -> Merge results -> Return
            |
            +-- Relationships? -> Graphiti (search_entities/search_facts)
            +-- Semantic? -> Graphiti + SQLite
            +-- Code? -> livegrep (code_search/search_function/search_class)
            +-- Exact match? -> SQLite FTS
            +-- Session context? -> Redis
```

### Multi-Tier Search Flow

When `memory_search` is called with `type="hybrid"`:

```
memory_search(query, type="hybrid")
       |
       v
+---------------+
| TierManager   |
+---------------+
       |
       +---> Redis (hot) -----> Cached results
       |
       +---> Graphiti (warm) -> Entity/relationship matches
       |
       +---> SQLite (cold) ---> Full-text search results
       |
       +---> livegrep (cold) -> Code search results
       |
       v
+---------------+
| Deduplicate   |
| Apply Filters |
| Merge Results |
+---------------+
       |
       v
  Return results
```

### Tier Promotion/Demotion

Access patterns drive automatic tier management:

```
                    Access Frequency
                          |
    +---------------------+---------------------+
    |                     |                     |
    v                     |                     v
+--------+           +----------+           +--------+
|  Hot   |<--promote-|   Warm   |<--promote-|  Cold  |
| Redis  |--demote-->| Graphiti |--demote-->| SQLite |
+--------+           +----------+           +--------+
```

**Promotion criteria:**
- Accessed >= 5 times total -> promote to warm (Graphiti)
- Content size >= 100 bytes
- Graphiti must be available

**AccessTracker implementation:**
- LRU eviction with max 10,000 entries
- Redis distributed tracking when available
- Local OrderedDict fallback

**Demotion criteria:**
- Not accessed in 24h -> demote from hot
- Not accessed in 7d -> demote from warm

## Handler Architecture

Each handler manages a category of tools:

```
BaseHandler (common dependencies)
    |
    +-- MemoryHandler
    |   +-- store(), search(), recall(), delete(), list()
    |
    +-- SessionHandler
    |   +-- save(), restore()
    |
    +-- VaultHandler
    |   +-- write(), read()
    |
    +-- StatsHandler
    |   +-- get_stats() with tier health checks
    |
    +-- ResearchHandler
    |   +-- session_start(), session_end()
    |   +-- transcript_store(), capture_store()
    |   +-- search()
    |
    +-- TierHandler
        +-- search_entities(), search_facts()
        +-- code_search(), search_function(), search_class()
```

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

## Async Operations

All async operations use the `run_async()` utility with configurable timeouts:

```python
from .async_utils import run_async

# Default timeout: 30 seconds
result = run_async(
    graphiti.search_entities(query),
    timeout=30.0
)
```

**Timeout configuration:**
| Operation | Default Timeout |
|-----------|-----------------|
| General async | 30 seconds |
| Graphiti search | 30 seconds |
| Tier promotion | 60 seconds |

## Graceful Degradation

The system operates with reduced functionality when optional components are unavailable:

| Missing Component | Impact | Fallback |
|-------------------|--------|----------|
| Redis | No hot cache | Direct SQLite queries |
| Graphiti | No relationship queries | Tag-based filtering |
| livegrep | No cross-repo code search | Local grep |
| Embeddings | No vector similarity | Keyword matching |

**Tier-specific tool behavior when unavailable:**
- `search_entities` / `search_facts` -> Return empty results
- `code_search` / `search_function` / `search_class` -> Return empty results

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

## OpenClaw Integration

OpenClaw provides multi-channel access to Claude with shared memory:

```
+---------------------------------------------------------------------+
|                     OpenClaw Gateway                                 |
+---------------------------------------------------------------------+
|  Channel Adapters                                                    |
|  +----------+ +----------+ +---------+ +--------+ +---------------+  |
|  | WhatsApp | | Telegram | | Discord | | Slack  | |   iMessage    |  |
|  | Baileys  | | Bot API  | | Bot API | | Bolt   | | BlueBubbles   |  |
|  +----+-----+ +----+-----+ +----+----+ +---+----+ +-------+-------+  |
|       |            |            |          |              |          |
|       +------------+------+-----+----------+--------------+          |
|                           |                                          |
|                  +--------v--------+                                 |
|                  |  Agent Router   |                                 |
|                  +--------+--------+                                 |
|                           |                                          |
|           +---------------+---------------+                          |
|           |                               |                          |
|  +--------v--------+            +--------v--------+                  |
|  | memory-mcp-     |            |   LLM Provider  |                  |
|  | bridge          |            |   (Anthropic)   |                  |
|  +--------+--------+            +-----------------+                  |
|           |                                                          |
+---------------------------------------------------------------------+
            |
            v
+---------------------------------------------------------------------+
|                      Memory MCP Server                               |
|                   (Shared with Claude Code)                          |
+---------------------------------------------------------------------+
```

### Memory Bridge Flow

1. **Incoming message** arrives via channel (e.g., WhatsApp)
2. **Auto-Recall**: Memory bridge searches for relevant context
3. **Context injection**: Relevant memories prepended to prompt
4. **LLM processing**: Claude generates response with context
5. **Auto-Capture**: Important info from conversation stored
6. **Response delivery**: Message sent back to channel

### Shared Memory Benefits

- **Continuity**: Preferences set in terminal available in WhatsApp
- **Knowledge transfer**: Decisions made via Discord visible in Claude Code
- **Research mobility**: Start in terminal, continue on phone
- **Team collaboration**: Share context across channels

## Related Pages

- [[Memory-MCP]] - Detailed Memory MCP documentation
- [[Memory-MCP-Tools]] - Complete tool reference (all 20 tools)
- [[Memory-Tiers]] - Deep dive on tier architecture
- [[OpenClaw]] - Multi-channel gateway setup
- [[Configuration]] - Customizing the architecture
