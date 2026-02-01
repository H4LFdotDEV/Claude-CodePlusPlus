# Memory Tiers

Deep dive into the tiered storage architecture with automatic promotion and multi-tier search.

## Overview

Claude Code++ uses a tiered storage system optimized for different access patterns:

```
┌─────────────────────────────────────────────────────────┐
│                    Hot Tier (Redis)                      │
│                     < 1ms access                         │
│              Session cache, frequent items               │
├─────────────────────────────────────────────────────────┤
│                   Warm Tier (Graphiti)                   │
│                    < 50ms access                         │
│              Knowledge graph, relationships              │
├─────────────────────────────────────────────────────────┤
│                   Cold Tier                              │
│   ┌─────────────────────┬─────────────────────┐        │
│   │  SQLite FTS         │   livegrep          │        │
│   │   < 50ms access     │   < 100ms access    │        │
│   │   Full-text, meta   │   Code search       │        │
│   └─────────────────────┴─────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│                 Archive Tier (Vault)                     │
│                    < 200ms access                        │
│              Human-readable documentation                │
└─────────────────────────────────────────────────────────┘
```

## Hot Tier: Redis

### Characteristics

| Property | Value |
|----------|-------|
| Storage | Redis |
| Latency | < 1ms |
| Capacity | ~1000 items |
| Persistence | Session-scoped |
| Requirement | Optional |

### Use Cases

- Current session state
- Recently accessed memories
- Frequently used context
- Working file list
- Query result caching

### Data Stored

```python
# Session state
session:{session_id} → {
    "project_path": "/path",
    "active_files": [...],
    "context": {...}
}

# Hot memories
memory:{doc_id} → serialized document

# Access tracking (distributed)
access:{doc_id} → {
    "count": 5,
    "last_access": "2024-01-15T10:30:00Z",
    "content_size": 1500
}
```

### Configuration

```bash
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=optional
REDIS_DB=0
```

### When Unavailable

- Direct SQLite queries (slightly slower)
- Access tracking uses local LRU cache
- Core functionality unaffected

---

## Warm Tier: Graphiti

### Characteristics

| Property | Value |
|----------|-------|
| Storage | Neo4j graph database |
| Latency | < 50ms |
| Capacity | Unlimited (relationship-based) |
| Persistence | Permanent |
| Requirement | Optional |

### Use Cases

- Entity relationships ("User prefers dark mode")
- Decision tracking ("What led to choosing JWT?")
- Conceptual connections
- "Who/what/when/where" queries

### Data Model

```cypher
// Entities
(:User)-[:PREFERS]->(:DarkMode)
(:Project {name: "api-gateway"})-[:USES]->(:JWT)

// Facts with temporal validity
(:Decision {
  content: "Chose JWT for authentication",
  timestamp: 2024-01-15,
  valid_at: 2024-01-15,
  invalid_at: null
})
```

### Dedicated Tools

- `search_entities` - Find entities by semantic search
- `search_facts` - Find relationships and facts

### Configuration

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
GRAPHITI_ENABLED=true
```

### When Unavailable

- `search_entities` and `search_facts` return empty results
- Fall back to tag-based filtering via SQLite
- Multi-tier search skips warm tier

---

## Cold Tier: SQLite

### Characteristics

| Property | Value |
|----------|-------|
| Storage | SQLite database |
| Latency | < 50ms |
| Capacity | Unlimited |
| Persistence | Permanent |
| Requirement | **Required** |

### Use Cases

- Metadata storage backbone
- Full-text search (FTS5)
- Document indexing
- Access pattern tracking
- Tag and project filtering

### Schema

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    content TEXT,
    doc_type TEXT,
    source TEXT,
    tags TEXT,  -- JSON array
    project TEXT,
    importance REAL,
    created_at TEXT,
    updated_at TEXT,
    accessed_at TEXT,
    access_count INTEGER,
    metadata TEXT  -- JSON object
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
    content, source, tags, project
);
```

### Configuration

```bash
SQLITE_PATH=~/.claude-code-pp/memory/sqlite/memories.db
```

### Always Available

SQLite is the backbone - if it fails, memory is unavailable.

---

## Cold Tier: livegrep

### Characteristics

| Property | Value |
|----------|-------|
| Storage | Index files |
| Latency | < 100ms |
| Capacity | All indexed repositories |
| Persistence | Index-based |
| Requirement | Optional |

### Use Cases

- Cross-repository code search
- Finding function definitions
- Pattern matching in code
- Code archaeology

### Dedicated Tools

- `code_search` - RE2 regex search across codebases
- `search_function` - Find function/method definitions
- `search_class` - Find class/struct/interface definitions

### Queries

```python
# Find function definitions
code_search(query="async function.*authenticate")

# Find usages
code_search(query="authenticateRequest\\(")

# Search specific languages
code_search(query="class.*Controller", path_filter="*.ts")
```

### Configuration

```bash
LIVEGREP_URL=http://localhost:8910
LIVEGREP_INDEX_PATH=/path/to/index
```

### When Unavailable

- `code_search`, `search_function`, `search_class` return empty results
- Multi-tier search skips code search
- Fall back to local grep if needed

---

## Archive Tier: Vault

### Characteristics

| Property | Value |
|----------|-------|
| Storage | Markdown files |
| Latency | < 200ms |
| Capacity | Unlimited |
| Persistence | Permanent |
| Requirement | **Required** |

### Use Cases

- Human-readable documentation
- Long-form notes
- Shareable content
- Version-controlled knowledge
- Research session outputs

### Directory Structure

```
vault/
├── code/           # Code snippets
├── notes/          # General notes
├── conversations/  # Conversation logs
├── references/     # Documentation
├── daily/          # Daily notes
└── research/       # Research sessions
    └── 2024-01-15-session-name/
        ├── session.md
        ├── transcript.md
        ├── insights.md
        └── captures/
```

### File Format

```markdown
---
tags:
  - architecture
  - auth
project: api-gateway
created: 2024-01-15
type: reference
---

# Authentication Architecture

## Overview
...
```

### Configuration

```bash
OBSIDIAN_VAULT_PATH=~/.claude-code-pp/memory/vault
```

---

## Tier Selection Logic

### Automatic Routing

The TierManager automatically routes queries to appropriate tiers:

```python
def search_all_tiers(query, limit, search_type):
    results = []
    seen_ids = set()

    # Tier 1: Hot (Redis cache)
    if redis and search_type != "semantic":
        cached = search_redis_cache(query)
        results.extend(cached)

    # Tier 2: Warm (Graphiti knowledge graph)
    if graphiti and len(results) < limit:
        entities = search_graphiti(query, limit)
        results.extend(entities)

    # Tier 3: Cold (SQLite FTS)
    if len(results) < limit:
        docs = sqlite.search_fulltext(query, limit)
        results.extend(docs)

    # Tier 4: Cold (livegrep - optional)
    if livegrep and len(results) < limit:
        code_results = search_livegrep(query, limit)
        results.extend(code_results)

    return deduplicated(results)[:limit]
```

### Query Pattern Hints

| Pattern | Routes To | Tool |
|---------|-----------|------|
| "how does X relate to Y" | Graphiti | `search_entities`/`search_facts` |
| "similar to", "like when" | Graphiti + SQLite | `memory_search` |
| "where is X defined" | livegrep | `search_function`/`search_class` |
| Exact keywords | SQLite FTS | `memory_search` |
| Code patterns | livegrep | `code_search` |

---

## Automatic Promotion and Demotion

### Promotion Criteria

Documents are promoted from cold to warm tier when:

1. **Access count >= 5** - Accessed 5+ times total
2. **Content size >= 100 bytes** - Minimum size for entity extraction
3. **Graphiti available** - Knowledge graph must be configured

### How Promotion Works

```python
# AccessTracker tracks each memory_recall
def record_access(doc_id, content_size):
    stats = get_stats(doc_id)
    stats.access_count += 1
    stats.content_size = content_size

    # Check for promotion
    if should_promote_to_warm(doc_id):
        promote_to_warm(doc_id)

# Promotion extracts entities and adds to knowledge graph
def promote_to_warm(doc_id):
    doc = sqlite.get(doc_id)
    graphiti.add_memory(
        content=doc.content,
        source=doc.source,
        doc_type=doc.doc_type
    )
```

### AccessTracker Implementation

The AccessTracker uses an LRU (Least Recently Used) cache:

- **Max entries**: 10,000 (configurable)
- **Eviction**: Oldest entries removed when limit reached
- **Distributed**: Uses Redis when available
- **Fallback**: Local OrderedDict when Redis unavailable

```python
class AccessTracker:
    def __init__(self, max_cache_size=10000):
        # OrderedDict for LRU eviction
        self._local_cache = OrderedDict()

    def record_access(self, doc_id, size):
        if doc_id in self._local_cache:
            # Move to end (most recently used)
            self._local_cache.move_to_end(doc_id)
        else:
            # Evict oldest if full
            while len(self._local_cache) >= self._max_cache_size:
                self._local_cache.popitem(last=False)
            self._local_cache[doc_id] = AccessStats(doc_id)

        self._local_cache[doc_id].record_access(size)
```

### Demotion Rules

```
Hot → Warm:
  - Not accessed in 24 hours
  - Session ends
  - Removed from Redis cache

Warm → Cold:
  - Not accessed in 7 days
  - Relationships maintained in Graphiti
  - Embeddings may be archived
```

---

## Performance Comparison

| Tier | Read | Write | Search | Best For |
|------|------|-------|--------|----------|
| Redis | 0.5ms | 0.5ms | 1ms | Active session |
| Graphiti | 20ms | 100ms | 50ms | Relationships |
| SQLite | 10ms | 20ms | 50ms | Full-text |
| livegrep | N/A | N/A | 100ms | Code search |
| Vault | 50ms | 100ms | N/A | Documentation |

### Latency Thresholds

| Tier | Expected | Concern Threshold |
|------|----------|-------------------|
| Redis | <1ms | >10ms |
| Graphiti | <50ms | >200ms |
| SQLite | <50ms | >200ms |
| livegrep | <100ms | >500ms |
| Vault | <200ms | >1s |

Use `memory_stats` to check latencies and identify issues.

---

## Graceful Degradation

| Missing | Impact | Fallback |
|---------|--------|----------|
| Redis | No hot cache | Direct SQLite, local access tracking |
| Graphiti | No relationships | Tag filtering, SQLite FTS |
| livegrep | No code search | Local grep |
| Embeddings | No semantic search | Full-text only |

**Core (SQLite + Vault) is always required.**

### Checking Availability

Use `memory_stats` to check tier health:

```json
{
  "tiers": {
    "hot": {"available": true, "stats": {...}},
    "warm": {"available": true, "stats": {...}},
    "cold": {"available": true, "stats": {...}},
    "code_search": {"available": false, "stats": {...}}
  },
  "health": {
    "tier_manager": {
      "status": "healthy",
      "available_tiers": ["hot", "warm", "cold"]
    }
  }
}
```

---

## Async Operations

All tier operations use the `run_async()` utility with configurable timeouts:

### Timeout Configuration

| Operation | Default Timeout |
|-----------|-----------------|
| General async | 30 seconds |
| Graphiti search | 30 seconds |
| Tier promotion | 60 seconds |

### Handling Timeouts

```python
from .async_utils import run_async

try:
    result = run_async(
        graphiti.search_entities(query),
        timeout=30.0
    )
except asyncio.TimeoutError:
    logger.warning("Graphiti search timed out")
    result = []  # Fallback to empty
```

---

## Configuration Summary

### Environment Variables

```bash
# Hot Tier
REDIS_URL=redis://localhost:6379

# Warm Tier
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Cold Tier
SQLITE_PATH=~/.claude-code-pp/memory/memories.db
LIVEGREP_URL=http://localhost:8910

# Archive Tier
OBSIDIAN_VAULT_PATH=~/.claude-code-pp/memory/vault
```

### settings.yaml

```yaml
tier_promotion:
  threshold: 5           # Access count for promotion
  min_size: 100          # Minimum content size (bytes)
  demotion_ttl_hours: 168  # 1 week

access_tracker:
  max_cache_size: 10000  # LRU eviction limit
```

---

## Related Pages

- [[Architecture]] - System overview
- [[Memory-MCP]] - Memory system docs
- [[Memory-MCP-Tools]] - Tool reference
- [[Configuration]] - Setup options
