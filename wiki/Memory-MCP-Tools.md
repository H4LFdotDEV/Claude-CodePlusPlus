# Memory MCP Tools Reference

Complete reference for all 20 Memory MCP tools with parameters, examples, and best practices.

## Tool Categories

| Category | Count | Tools |
|----------|-------|-------|
| Core | 10 | memory_store, memory_search, memory_recall, memory_delete, memory_list, session_save, session_restore, vault_write, vault_read, memory_stats |
| Research | 5 | research_session_start, research_session_end, research_transcript_store, research_capture_store, research_search |
| Tier-Specific | 5 | search_entities, search_facts, code_search, search_function, search_class |

---

## Core Tools (10)

### memory_store

Store content in persistent memory.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The content to store |
| `type` | enum | Yes | One of: `code`, `note`, `conversation`, `reference` |
| `source` | string | Yes | Origin identifier (file path, URL, etc.) |
| `tags` | array[string] | No | Categorization tags |
| `project` | string | No | Project association |

#### Examples

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

#### Best Practices

- Include both the problem AND solution for errors
- Use consistent tag naming (kebab-case recommended)
- Always include project for project-specific content
- Summarize long content, store details in vault

---

### memory_search

Search memory using text, semantic, or hybrid search. Uses multi-tier search when TierManager is available.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `type` | enum | No | `text`, `semantic`, or `hybrid` (default: `hybrid`) |
| `limit` | integer | No | Maximum results (default: 10, max: 100) |
| `filters` | object | No | Filter criteria |

#### Filter Options

```json
{
  "filters": {
    "doc_type": "code",
    "project": "api-gateway",
    "tags": ["auth", "error"]
  }
}
```

#### Examples

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

#### Search Type Selection

| Use | When |
|-----|------|
| `text` | Exact keywords, error messages, variable names |
| `semantic` | Conceptual queries, "find similar", different wording |
| `hybrid` | Best of both, most accurate, slightly slower |

#### Multi-Tier Behavior

When using `hybrid` or `semantic` search with TierManager available:
1. Hot tier (Redis) checked first
2. Warm tier (Graphiti) for relationship matches
3. Cold tier (SQLite FTS) for text matches
4. Cold tier (livegrep) for code matches
5. Results deduplicated and merged

---

### memory_recall

Retrieve a specific memory by ID. **Tracks access for tier promotion** - after 5+ accesses, documents are promoted to the warm tier (Graphiti knowledge graph).

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Document ID |

#### Example

```json
{
  "id": "mem_abc123def456"
}
```

#### Returns

Full document including:
- Content
- Metadata (type, source, tags, project)
- Timestamps (created, updated, accessed)
- Access statistics

---

### memory_delete

Remove a memory from all storage tiers.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Document ID to delete |

#### Example

```json
{
  "id": "mem_old_preference_123"
}
```

#### Best Practices

- Search first to verify you're deleting the right memory
- Use when information is superseded, not just old
- Store replacement before deleting if updating

---

### memory_list

List memories with optional filters.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Maximum results (default: 20, max: 100) |
| `type` | string | No | Filter by doc_type |
| `project` | string | No | Filter by project |

#### Examples

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

#### Use Cases

- Session start: Get overview of recent activity
- Project switch: What do I know about this project?
- Cleanup: Find old memories to review/delete

---

### session_save

Persist current session state for later restoration.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_path` | string | Yes | Project directory path |
| `active_files` | array[string] | No | Files being worked on |
| `context` | object | No | Custom context data |

#### Examples

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

#### Best Practices

- Save at natural stopping points
- Include active files for quick resumption
- Document current task and next steps in context
- Save before switching projects

---

### session_restore

Restore a previous session's state.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No | Specific session ID (latest if omitted) |

#### Examples

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

#### Returns

- Active files list
- Custom context
- Recent memory IDs
- Session timestamps

---

### vault_write

Write a note to the Obsidian-compatible vault.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Note path (without .md extension) |
| `content` | string | Yes | Markdown content |
| `folder` | enum | No | One of: `code`, `notes`, `conversations`, `references`, `daily` |
| `tags` | array[string] | No | Tags for the note |

#### Examples

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

#### Best Practices

- Use for content that should be human-readable
- Great for documentation summaries
- Can be version controlled separately
- Accessible outside Claude

---

### vault_read

Read a note from the Obsidian vault.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Note path |

#### Examples

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

#### Returns

- Note content (markdown)
- Frontmatter metadata if present
- File timestamps

---

### memory_stats

Get memory system statistics and health information with tier-level details.

#### Parameters

None required.

#### Example

```json
{}
```

#### Returns

```json
{
  "sqlite_count": 150,
  "session_id": "current-session-id",
  "components": {
    "sqlite": true,
    "vault": true,
    "redis": true,
    "embedder": true,
    "tier_manager": true
  },
  "health": {
    "sqlite": {"status": "healthy", "latency_ms": 2.5},
    "vault": {"status": "connected", "latency_ms": 15.3},
    "redis": {"status": "healthy", "latency_ms": 0.8},
    "embedder": {"status": "active"},
    "tier_manager": {"status": "healthy", "latency_ms": 5.2, "available_tiers": ["hot", "warm", "cold", "code_search"]}
  },
  "tiers": {
    "hot": {"available": true, "stats": {...}},
    "warm": {"available": true, "stats": {...}},
    "cold": {"available": true, "stats": {...}},
    "code_search": {"available": true, "stats": {...}}
  },
  "redis": {
    "connected": true,
    "used_memory": "1.5M",
    "cache_hits": 45,
    "cache_misses": 12
  }
}
```

#### Use Cases

- Verify components are available
- Debug slow operations
- Monitor system health
- Check tier availability

---

## Research Tools (5)

### research_session_start

Start a new research session for voice conversation and whiteboard capture.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Session name |
| `focus_area` | string | No | Research focus or topic |
| `participants` | array[string] | No | List of participants |

#### Example

```json
{
  "name": "Pocket Dimension Physics",
  "focus_area": "Quantum mechanics fundamentals",
  "participants": ["Jeremiah", "Claude"]
}
```

#### Returns

- Session ID
- Session metadata
- Status: "active"

---

### research_session_end

End a research session and generate summary.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID to end |
| `summary` | string | No | Session summary |
| `action_items` | array[string] | No | List of action items |
| `key_decisions` | array[string] | No | Key decisions made |

#### Example

```json
{
  "session_id": "uuid-of-session",
  "summary": "Explored quantum entanglement concepts and their applications",
  "action_items": ["Research Bell's theorem", "Create visualization prototype"],
  "key_decisions": ["Focus on practical quantum computing applications"]
}
```

#### Returns

- Session summary
- Duration in minutes
- Transcript/capture counts
- Vault path where session was saved

---

### research_transcript_store

Store a voice transcript segment from a research session.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Transcript text |
| `speaker` | string | No | Speaker name (default: "user") |
| `session_id` | string | No | Associated research session |
| `timestamp` | string | No | ISO timestamp of the segment |

#### Example

```json
{
  "text": "The key insight here is that quantum states can be correlated even when physically separated.",
  "speaker": "Jeremiah",
  "session_id": "uuid-of-session",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### research_capture_store

Store a whiteboard or webcam capture from a research session.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `description` | string | Yes | Description of what was captured |
| `ocr_text` | string | No | Extracted text from the image |
| `image_path` | string | No | Path to the image file |
| `session_id` | string | No | Associated research session |
| `capture_type` | enum | No | `whiteboard`, `webcam`, or `screenshot` (default: whiteboard) |

#### Example

```json
{
  "description": "Diagram showing quantum state superposition with Bloch sphere",
  "ocr_text": "State |psi> = alpha|0> + beta|1>",
  "image_path": "/path/to/capture.png",
  "session_id": "uuid-of-session",
  "capture_type": "whiteboard"
}
```

---

### research_search

Search across research data including transcripts, captures, and sessions.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `session_id` | string | No | Filter to specific session |
| `type` | enum | No | `transcript`, `research_image`, or `research_session` |
| `limit` | integer | No | Maximum results (default: 20) |

#### Example

```json
{
  "query": "quantum entanglement",
  "session_id": "optional-session-id",
  "type": "transcript",
  "limit": 20
}
```

---

## Tier-Specific Tools (5)

### search_entities

Search the Graphiti knowledge graph for entities (people, concepts, projects, etc).

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `limit` | integer | No | Max results (default: 10, max: 100) |

#### Example

```json
{
  "query": "user preferences",
  "limit": 10
}
```

#### Returns

```json
{
  "results": [
    {
      "id": "entity-uuid",
      "name": "UserPreferences",
      "summary": "User's coding preferences including TypeScript, functional programming",
      "labels": ["User", "Preference", "Configuration"]
    }
  ],
  "total": 1
}
```

#### When to Use

- Understanding entity relationships
- Finding concepts mentioned across conversations
- "Who/what" questions about past work

---

### search_facts

Search the Graphiti knowledge graph for facts and relationships between entities.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `limit` | integer | No | Max results (default: 10, max: 100) |

#### Example

```json
{
  "query": "decided to use JWT",
  "limit": 10
}
```

#### Returns

```json
{
  "results": [
    {
      "id": "fact-uuid",
      "source": "api-gateway-project",
      "target": "JWT",
      "fact": "Project decided to use JWT for authentication due to stateless scaling requirements",
      "valid_at": "2024-01-15",
      "invalid_at": null
    }
  ],
  "total": 1
}
```

#### When to Use

- Tracing decision history
- Understanding "why" questions
- Finding relationships between concepts

---

### code_search

Search code across all indexed repositories using RE2 regex patterns.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | RE2 regex pattern to search for |
| `path_filter` | string | No | Glob pattern to filter files (e.g., `*.py`) |
| `repo_filter` | string | No | Repository name to search within |
| `limit` | integer | No | Max results (default: 50, max: 200) |

#### Examples

**Search for async authentication functions:**
```json
{
  "query": "async function.*authenticate",
  "path_filter": "*.ts",
  "limit": 50
}
```

**Search in specific repository:**
```json
{
  "query": "class.*Controller",
  "repo_filter": "api-gateway",
  "path_filter": "*.java",
  "limit": 100
}
```

#### Returns

```json
{
  "results": [
    {
      "repo": "api-gateway",
      "path": "src/auth/middleware.ts",
      "line_number": 42,
      "line_content": "async function authenticateRequest(req, res, next) {"
    }
  ],
  "total": 1,
  "truncated": false,
  "duration_ms": 15
}
```

#### RE2 Regex Tips

- Use `.*` for wildcards
- `\s+` for whitespace
- `\w+` for word characters
- Escape special chars: `\(`, `\)`, `\{`, `\}`

---

### search_function

Find function or method definitions by name across codebases.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Function name to search for |
| `language` | string | No | Programming language |
| `limit` | integer | No | Max results (default: 50, max: 200) |

#### Supported Languages

`python`, `javascript`, `typescript`, `go`, `rust`, `java`, `c`, `cpp`

#### Examples

**Find function in TypeScript:**
```json
{
  "name": "authenticateRequest",
  "language": "typescript",
  "limit": 50
}
```

**Find function in any language:**
```json
{
  "name": "validateToken"
}
```

#### Language Patterns

| Language | Pattern |
|----------|---------|
| Python | `def functionName` or `async def functionName` |
| JavaScript/TypeScript | `function functionName` or `const functionName =` |
| Go | `func functionName` or `func (receiver) functionName` |
| Rust | `fn functionName` or `pub fn functionName` |
| Java | `void functionName` or `public ... functionName` |
| C/C++ | Return type followed by `functionName(` |

---

### search_class

Find class, struct, or interface definitions by name across codebases.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Class/struct name to search for |
| `language` | string | No | Programming language |
| `limit` | integer | No | Max results (default: 50, max: 200) |

#### Supported Languages

`python`, `javascript`, `typescript`, `go`, `rust`, `java`

#### Examples

**Find class in TypeScript:**
```json
{
  "name": "AuthMiddleware",
  "language": "typescript",
  "limit": 50
}
```

**Find struct in Go:**
```json
{
  "name": "UserConfig",
  "language": "go"
}
```

#### Language Patterns

| Language | Pattern |
|----------|---------|
| Python | `class ClassName` |
| JavaScript/TypeScript | `class ClassName` or `interface ClassName` |
| Go | `type ClassName struct` |
| Rust | `struct ClassName` or `impl ClassName` |
| Java | `class ClassName` or `interface ClassName` |

---

## Best Practices Summary

### Core Tools

| Tool | Do | Don't |
|------|----|----|
| `memory_store` | Store preferences, decisions, solutions | Store ephemeral chat, duplicates |
| `memory_search` | Search before answering context questions | Skip searching and guess |
| `memory_recall` | Track access for promotion | Ignore return value |
| `memory_delete` | Delete when information is superseded | Delete without checking first |
| `memory_list` | Use for orientation at session start | Ignore project filter |

### Tier-Specific Tools

| Tool | Use When | Fallback |
|------|----------|----------|
| `search_entities` | Understanding relationships | `memory_search` |
| `search_facts` | Tracing decisions | `memory_search` |
| `code_search` | Finding code patterns | Local grep |
| `search_function` | Finding function definitions | `code_search` with pattern |
| `search_class` | Finding class definitions | `code_search` with pattern |

### Research Tools

| Tool | Use When |
|------|----------|
| `research_session_start` | Beginning voice/whiteboard work |
| `research_transcript_store` | As transcripts come in |
| `research_capture_store` | When user shares visual content |
| `research_session_end` | Completing research session |
| `research_search` | Finding past research content |
