# Memory Tiers

Deep dive into the tiered storage architecture.

## Overview

Claude Code++ uses a tiered storage system optimized for different access patterns:

```
┌─────────────────────────────────────────────────────────┐
│                    Hot Tier (Redis)                      │
│                     < 1ms access                         │
│              Session cache, frequent items               │
├─────────────────────────────────────────────────────────┤
│                   Warm Tier                              │
│   ┌─────────────────────┬─────────────────────┐        │
│   │  Graphiti (Neo4j)   │   LanceDB           │        │
│   │   < 50ms access     │   < 10ms access     │        │
│   │   Relationships     │   Semantic search   │        │
│   └─────────────────────┴─────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│                   Cold Tier                              │
│   ┌─────────────────────┬─────────────────────┐        │
│   │  SQLite             │   livegrep          │        │
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

# Access tracking
access:{doc_id} → access count
```

### Configuration

```bash
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=optional
REDIS_DB=0
```

### When Unavailable

- Direct SQLite queries (slightly slower)
- No session caching
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

// Facts
(:Decision {
  content: "Chose JWT for authentication",
  timestamp: 2024-01-15
})
```

### Configuration

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
GRAPHITI_ENABLED=true
```

### When Unavailable

- Relationship queries return empty
- Fall back to tag-based filtering
- Semantic search still works via LanceDB

---

## Warm Tier: LanceDB

### Characteristics

| Property | Value |
|----------|-------|
| Storage | LanceDB (embedded) |
| Latency | < 10ms |
| Capacity | 100k+ vectors |
| Persistence | Permanent |
| Requirement | Optional |

### Use Cases

- Semantic similarity search
- "Find memories like X"
- Conceptual matching
- Content clustering

### How It Works

```
Content → Embedding Model → Vector → LanceDB
                              ↓
Query → Embedding → Nearest Neighbor Search → Results
```

### Configuration

```bash
LANCEDB_PATH=~/.claude-code-pp/memory/lancedb
EMBEDDING_PROVIDER=local  # or openai, voyage
```

### Embedding Providers

| Provider | Quality | Speed | Cost |
|----------|---------|-------|------|
| Local (nomic-embed) | Good | Fast | Free |
| OpenAI | Better | Medium | $$ |
| Voyage | Best | Medium | $$$ |

### When Unavailable

- Semantic search unavailable
- Fall back to full-text search
- Exact keyword matching only

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

- Metadata storage
- Full-text search (FTS5)
- Document indexing
- Access pattern tracking

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
    access_count INTEGER
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
LIVEGREP_ENABLED=true
LIVEGREP_URL=http://localhost:8910
LIVEGREP_INDEX_PATH=/path/to/index
```

### When Unavailable

- Code search limited to local grep
- Cross-repo search unavailable

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

### Directory Structure

```
vault/
├── code/           # Code snippets
├── notes/          # General notes
├── conversations/  # Conversation logs
├── references/     # Documentation
└── daily/          # Daily notes
```

### File Format

```markdown
---
tags:
  - architecture
  - auth
project: api-gateway
created: 2024-01-15
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

The system automatically routes queries to appropriate tiers:

```python
def select_tier(query, query_type):
    if mentions_relationships(query):
        return [Graphiti, SQLite]  # Relationship → Graphiti

    if is_semantic(query_type):
        return [LanceDB, SQLite]   # Semantic → LanceDB

    if is_code_query(query):
        return [livegrep, Grep]    # Code → livegrep

    return [SQLite]                # Default → SQLite FTS
```

### Manual Hints

Use query patterns to hint at tier selection:

| Pattern | Routes To |
|---------|-----------|
| "how does X relate to Y" | Graphiti |
| "similar to", "like when" | LanceDB |
| "where is X defined" | livegrep |
| Exact keywords | SQLite FTS |

---

## Promotion and Demotion

### Automatic Promotion

```
Cold → Warm:
  - Accessed > 5 times total
  - Added to LanceDB for semantic search

Warm → Hot:
  - Accessed > 3 times in current session
  - Cached in Redis
```

### Automatic Demotion

```
Hot → Warm:
  - Not accessed in 24 hours
  - Removed from Redis cache

Warm → Cold:
  - Not accessed in 7 days
  - Embeddings may be archived
```

### Access Tracking

Every memory access updates:
- `accessed_at` timestamp
- `access_count` counter

These drive promotion/demotion decisions.

---

## Performance Comparison

| Tier | Read | Write | Search | Best For |
|------|------|-------|--------|----------|
| Redis | 0.5ms | 0.5ms | 1ms | Active session |
| LanceDB | 5ms | 50ms | 10ms | Semantic |
| Graphiti | 20ms | 100ms | 50ms | Relationships |
| SQLite | 10ms | 20ms | 50ms | Full-text |
| livegrep | N/A | N/A | 100ms | Code |
| Vault | 50ms | 100ms | N/A | Docs |

---

## Graceful Degradation

| Missing | Impact | Fallback |
|---------|--------|----------|
| Redis | No hot cache | Direct SQLite |
| LanceDB | No semantic search | Full-text only |
| Graphiti | No relationships | Tag filtering |
| livegrep | No code search | Local grep |

**Core (SQLite + Vault) is always required.**

## Related Pages

- [[Architecture]] - System overview
- [[Memory-MCP]] - Memory system docs
- [[Configuration]] - Setup options
