# Memory MCP Tools Reference

Complete reference for all Memory MCP tools with parameters, examples, and best practices.

## memory_store

Store content in persistent memory.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The content to store |
| `type` | enum | Yes | One of: `code`, `note`, `conversation`, `reference` |
| `source` | string | Yes | Origin identifier (file path, URL, etc.) |
| `tags` | array[string] | No | Categorization tags |
| `project` | string | No | Project association |

### Examples

**Store a user preference:**
```json
{
  "content": "User prefers functional programming patterns. Avoid classes, use pure functions.",
  "type": "note",
  "source": "conversation:2024-01-15",
  "tags": ["preference", "coding-style", "functional"],
  "project": "user-profile"
}
```

**Store an error solution:**
```json
{
  "content": "TypeError in UserList.tsx:45 - async data not loaded. Fixed with loading state check.",
  "type": "code",
  "source": "src/components/UserList.tsx",
  "tags": ["error", "react", "async", "resolved"],
  "project": "dashboard-app"
}
```

**Store an architecture decision:**
```json
{
  "content": "Chose JWT over sessions. Reasons: stateless scaling, microservices support.",
  "type": "reference",
  "source": "architecture:auth-strategy",
  "tags": ["decision", "architecture", "auth"],
  "project": "api-gateway"
}
```

### Best Practices

- Include both the problem AND solution for errors
- Use consistent tag naming (kebab-case recommended)
- Always include project for project-specific content
- Summarize long content, store details in vault

---

## memory_search

Search memory using text, semantic, or hybrid search.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `type` | enum | No | `text`, `semantic`, or `hybrid` (default: `text`) |
| `limit` | integer | No | Maximum results (default: 10) |
| `filters` | object | No | Filter criteria |

### Filter Options

```json
{
  "filters": {
    "doc_type": "code",
    "project": "api-gateway",
    "tags": ["auth", "error"]
  }
}
```

### Examples

**Simple text search:**
```json
{
  "query": "authentication error",
  "type": "text",
  "limit": 5
}
```

**Semantic search for similar content:**
```json
{
  "query": "undefined property error in React",
  "type": "semantic",
  "limit": 10,
  "filters": {
    "doc_type": "code",
    "tags": ["error"]
  }
}
```

**Hybrid search with project filter:**
```json
{
  "query": "JWT implementation decisions",
  "type": "hybrid",
  "limit": 15,
  "filters": {
    "project": "api-gateway"
  }
}
```

### Search Type Selection

| Use | When |
|-----|------|
| `text` | Exact keywords, error messages, variable names |
| `semantic` | Conceptual queries, "find similar", different wording |
| `hybrid` | Best of both, most accurate, slightly slower |

---

## memory_recall

Retrieve a specific memory by ID.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Document ID |

### Example

```json
{
  "id": "mem_abc123def456"
}
```

### Returns

Full document including:
- Content
- Metadata (type, source, tags, project)
- Timestamps (created, updated, accessed)
- Access statistics

---

## memory_delete

Remove a memory from all storage tiers.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Document ID to delete |

### Example

```json
{
  "id": "mem_old_preference_123"
}
```

### Best Practices

- Search first to verify you're deleting the right memory
- Use when information is superseded, not just old
- Store replacement before deleting if updating

---

## memory_list

List memories with optional filters.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Maximum results (default: 20) |
| `type` | string | No | Filter by doc_type |
| `project` | string | No | Filter by project |

### Examples

**List recent memories:**
```json
{
  "limit": 20
}
```

**List code snippets for a project:**
```json
{
  "limit": 10,
  "type": "code",
  "project": "api-gateway"
}
```

**List all notes:**
```json
{
  "limit": 50,
  "type": "note"
}
```

### Use Cases

- Session start: Get overview of recent activity
- Project switch: What do I know about this project?
- Cleanup: Find old memories to review/delete

---

## session_save

Persist current session state for later restoration.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_path` | string | Yes | Project directory path |
| `active_files` | array[string] | No | Files being worked on |
| `context` | object | No | Custom context data |

### Examples

**Basic session save:**
```json
{
  "project_path": "/Users/dev/api-gateway"
}
```

**Full session save:**
```json
{
  "project_path": "/Users/dev/api-gateway",
  "active_files": [
    "src/auth/middleware.ts",
    "src/auth/jwt.ts",
    "tests/auth.test.ts"
  ],
  "context": {
    "current_task": "implementing JWT refresh",
    "completed": ["JWT verification", "access token generation"],
    "blockers": ["refresh token storage decision needed"],
    "next_steps": ["implement token blacklist", "add rotation endpoint"]
  }
}
```

### Best Practices

- Save at natural stopping points
- Include active files for quick resumption
- Document current task and next steps in context
- Save before switching projects

---

## session_restore

Restore a previous session's state.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No | Specific session ID (latest if omitted) |

### Examples

**Restore most recent session:**
```json
{}
```

**Restore specific session:**
```json
{
  "session_id": "sess_2024-01-15_api-gateway"
}
```

### Returns

- Active files list
- Custom context
- Recent memory IDs
- Session timestamps

---

## vault_write

Write a note to the Obsidian-compatible vault.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Note path (without .md extension) |
| `content` | string | Yes | Markdown content |
| `folder` | enum | No | One of: `code`, `notes`, `conversations`, `references`, `daily` |
| `tags` | array[string] | No | Tags for the note |

### Examples

**Project documentation:**
```json
{
  "path": "projects/api-gateway/architecture",
  "content": "# API Gateway Architecture\n\n## Overview\n...",
  "folder": "references",
  "tags": ["architecture", "api-gateway"]
}
```

**Daily note:**
```json
{
  "path": "daily/2024-01-15",
  "content": "# 2024-01-15\n\n## Completed\n- JWT refresh tokens\n...",
  "folder": "daily",
  "tags": ["daily", "api-gateway"]
}
```

**Code snippet:**
```json
{
  "path": "code/retry-pattern",
  "content": "# Retry Pattern\n\n```typescript\nasync function retry<T>...\n```",
  "folder": "code",
  "tags": ["pattern", "typescript", "reliability"]
}
```

### Best Practices

- Use for content that should be human-readable
- Great for documentation summaries
- Can be version controlled separately
- Accessible outside Claude

---

## vault_read

Read a note from the Obsidian vault.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Note path |

### Examples

```json
{
  "path": "references/projects/api-gateway/architecture"
}
```

```json
{
  "path": "daily/2024-01-15"
}
```

### Returns

- Note content (markdown)
- Frontmatter metadata if present
- File timestamps

---

## memory_stats

Get memory system statistics and health information.

### Parameters

None required.

### Example

```json
{}
```

### Returns

```json
{
  "sqlite_count": 150,
  "session_id": "current-session-id",
  "components": {
    "sqlite": true,
    "vault": true,
    "redis": true,
    "graphiti": false,
    "lancedb": true,
    "livegrep": false,
    "embedder": true
  },
  "health": {
    "sqlite": {"status": "healthy", "latency_ms": 2.5},
    "vault": {"status": "connected", "latency_ms": 15.3},
    "redis": {"status": "healthy", "latency_ms": 0.8},
    "embedder": {"status": "active", "provider": "local/nomic-embed"}
  },
  "redis": {
    "connected": true,
    "used_memory": "1.5M",
    "cache_hits": 45,
    "cache_misses": 12
  }
}
```

### Use Cases

- Verify components are available
- Debug slow operations
- Monitor system health

---

## Knowledge Graph Tools (Graphiti)

When Graphiti is enabled, additional tools are available:

### search_entities

Search for entities in the knowledge graph.

```json
{
  "query": "user preferences",
  "limit": 10
}
```

### search_facts

Search for relationships/facts between entities.

```json
{
  "query": "decided to use JWT",
  "limit": 10
}
```

---

## Code Search Tools (livegrep)

When livegrep is enabled:

### code_search

Search code across repositories.

```json
{
  "query": "async function.*retry",
  "path_filter": "*.ts",
  "max_matches": 20
}
```

### search_function

Find function definitions.

```json
{
  "function_name": "authenticateRequest",
  "language": "typescript"
}
```

### search_class

Find class definitions.

```json
{
  "class_name": "AuthMiddleware",
  "language": "typescript"
}
```
