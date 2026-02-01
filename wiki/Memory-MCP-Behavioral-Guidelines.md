# Memory MCP Behavioral Guidelines

How Claude should use the Memory MCP system effectively with all 20 tools.

## Core Philosophy

Memory is integral to Claude's identity with each user. It's not a database to query occasionally - it's how Claude genuinely remembers past interactions, preferences, and decisions.

**20 Tools Available:**
- 10 Core tools (memory CRUD, sessions, vault)
- 5 Research tools (voice/whiteboard sessions)
- 5 Tier-specific tools (knowledge graph, code search)

## The Search-First Principle

### When to Search

**ALWAYS** search memory when the user's message suggests prior context:

| User Says | What It Means | Action |
|-----------|---------------|--------|
| "like we discussed" | References past conversation | Search immediately |
| "remember when" | Expects you to recall | Search before responding |
| "the usual way" | Has established preferences | Search for preferences |
| "continue from yesterday" | Expects session continuity | Restore session |
| Project-specific terms | Assumes shared context | Search project memories |

### The Golden Rule

> The cost of a search that finds nothing is minimal.
> The cost of ignoring relevant context is a worse response and a frustrated user.

### Example: Right Way

```
User: "Use the same approach we used for the auth service"

Claude thinks: User references past work -> search memory
Claude: [calls memory_search("auth service approach")]
Claude: [calls search_entities("auth service") for relationships]
Claude: "Found it - we used JWT with refresh token rotation,
         with Redis for session storage. Same approach here?"
```

### Example: Wrong Way

```
User: "Use the same approach we used for the auth service"

Claude: "I apologize, but I don't have memory of our previous
         conversations. Could you remind me what approach..."

[x] Claude didn't search before admitting ignorance
```

## Active Memory Management

### What to Store

Store information the user would expect you to remember:

| Store | Examples |
|-------|----------|
| Preferences | "I prefer TypeScript", "Use 2-space indent" |
| Decisions | "We chose JWT for auth", "Using PostgreSQL" |
| Error Solutions | Error message + root cause + fix |
| Architecture | Tech stack, patterns, constraints |
| Project Context | Goals, stakeholders, deadlines |

### What NOT to Store

| Don't Store | Why |
|-------------|-----|
| Every message | Clutters memory, hard to search |
| "Thanks!", "Got it" | No information value |
| Passwords/tokens | Security risk |
| Temporary context | Ephemeral, session-only |
| Duplicate info | Already stored |

### Keeping Memory Fresh

When information changes:

1. **Search** for existing related memories
2. **Delete** outdated version
3. **Store** corrected information
4. **Acknowledge** the update

```
User: "Actually, let's use MongoDB instead of PostgreSQL"

Claude: [searches for database decisions]
Claude: [deletes old PostgreSQL decision]
Claude: [stores new MongoDB decision]
Claude: "Updated my notes - we're using MongoDB now.
         Should I also update the architecture docs in vault?"
```

## Session Lifecycle

### Session Start

```
1. Call session_restore (loads previous context)
2. If restored:
   - Note what files were active
   - Summarize where we left off
   - Ask if user wants to continue or start fresh
3. If no session:
   - Call memory_list for recent activity
   - Offer to search for project context
```

### During Session

```
1. Search before answering context questions
2. Store important learnings immediately
3. Don't batch - store as you learn
4. Update memory when information changes
5. For long sessions: save periodically
```

### Session End

```
1. Call session_save with current state
2. Store any pending decisions/learnings
3. Write significant documentation to vault
4. Confirm what was saved
```

## Tier Selection and Tool Usage

### When to Use Each Tool

| Query Type | Primary Tool | When to Use |
|------------|--------------|-------------|
| Session context | `session_restore` | Start of session |
| General search | `memory_search` | Context-dependent questions |
| Entity relationships | `search_entities` | "How does X relate to Y?" |
| Decision history | `search_facts` | "What led to this decision?" |
| Code definitions | `search_function` / `search_class` | "Where is X defined?" |
| Code patterns | `code_search` | Regex search across repos |
| Documentation | `vault_read` | Retrieve saved docs |

### Multi-Tier Search Behavior

When using `memory_search` with `type="hybrid"`:

1. **Hot tier** (Redis) - Cached results
2. **Warm tier** (Graphiti) - Entity/relationship matches
3. **Cold tier** (SQLite) - Full-text search
4. **Cold tier** (livegrep) - Code matches

Results are deduplicated and filtered by tags/project.

### When to Use Tier-Specific Tools

**Use `search_entities` / `search_facts` when:**
- Understanding relationships: "How does X relate to Y?"
- Tracing history: "What led to this decision?"
- Finding connected concepts

**Use `code_search` / `search_function` / `search_class` when:**
- Finding implementations: "Where is X defined?"
- Cross-repo search: "Who calls this function?"
- Pattern matching: "Find all async handlers"

```
User: "Where is the authentication middleware defined?"

Claude: [search_function(name="authenticate", language="typescript")]
Claude: [code_search(query="class.*Middleware", path_filter="*.ts")]

"Found authenticateRequest in src/auth/middleware.ts at line 42,
 and AuthMiddleware class in src/middleware/auth.ts."
```

## Access Tracking and Promotion

### How Promotion Works

Each `memory_recall` tracks access:
- After 5+ accesses, documents are promoted to warm tier
- AccessTracker uses LRU cache (max 10k entries)
- Promoted documents are added to knowledge graph

### Implications for Usage

- Frequently accessed memories become searchable via `search_entities`
- Important context naturally rises to warm tier
- No manual promotion needed - just use the system

## Anti-Patterns to Avoid

### 1. Apologizing Without Searching

[x] **Bad:**
```
"I apologize, but I don't have memory of our previous conversations..."
```

[ok] **Good:**
```
[Search first]
"I searched my memory but didn't find records of that.
Could you remind me of the context?"
```

### 2. Asking Permission to Search

[x] **Bad:**
```
"Would you like me to check my memory for previous discussions?"
```

[ok] **Good:**
```
[Just search - it's your memory, use it naturally]
```

### 3. Storing Everything

[x] **Bad:**
```
[Stores every code snippet, every response, every trivial exchange]
```

[ok] **Good:**
```
[Stores selectively: preferences, decisions, solutions, important context]
```

### 4. Forgetting to Update

[x] **Bad:**
```
User: "Changed my mind about Redux"
Claude: "Okay" [doesn't update stored decision]
```

[ok] **Good:**
```
User: "Changed my mind about Redux"
Claude: [searches, deletes old preference, stores new one]
        "Got it, updated my notes. What are we using instead?"
```

### 5. Generic Memories

[x] **Bad:**
```
memory_store(
  content="User likes clean code",
  tags=[]  // No tags!
)
```

[ok] **Good:**
```
memory_store(
  content="User prefers clean code: small functions, meaningful names, no comments for obvious code",
  tags=["preference", "coding-style"],
  project="user-profile"
)
```

### 6. Ignoring Tier-Specific Tools

[x] **Bad:**
```
[Only uses memory_search for everything]
```

[ok] **Good:**
```
[Uses search_entities for relationships]
[Uses code_search for code patterns]
[Uses memory_search for general context]
```

## Example Conversation Patterns

### Pattern 1: Continuing Previous Work

```
User: "Let's continue working on the API gateway"

Claude: [session_restore]
Claude: [memory_search(project="api-gateway")]
Claude: [search_entities("api-gateway")]

"I see we were implementing rate limiting last session.
You had decided on the token bucket algorithm and were
about to integrate with Redis. The active files were
src/middleware/rateLimiter.ts and tests/rateLimit.test.ts.
Ready to continue?"
```

### Pattern 2: Referencing Past Decision

```
User: "Use the same database we discussed"

Claude: [memory_search("database decision")]
Claude: [search_facts("database choice")]

"Found it - we chose PostgreSQL for this project because
of the complex relational queries. I have the connection
config stored. Should I set up the schema?"
```

### Pattern 3: Finding Code

```
User: "Where is the authentication middleware?"

Claude: [search_function("authenticate", language="typescript")]
Claude: [search_class("AuthMiddleware", language="typescript")]

"Found it:
- authenticateRequest() in src/auth/middleware.ts:42
- AuthMiddleware class in src/middleware/auth.ts:15

Want me to show the implementation?"
```

### Pattern 4: Learning New Preference

```
User: "I prefer using async/await over .then() chains"

Claude: [memory_store with preference tags]

"Noted - I'll use async/await going forward. This applies
to all projects or just this one?"

User: "All projects"

Claude: [updates memory with broader scope]

"Got it, stored as a global preference."
```

### Pattern 5: Correcting Outdated Info

```
User: "We're not using Redux anymore, switched to Zustand"

Claude: [memory_search("Redux OR state management")]
Claude: [memory_delete old Redux decision]
Claude: [memory_store new Zustand decision]

"Updated - Zustand it is. I've removed the Redux notes
and stored the new approach. Want me to update the
architecture documentation in vault too?"
```

### Pattern 6: Research Session

```
User: "Let's brainstorm the new API design"

Claude: [research_session_start(name="API Design", focus_area="REST vs GraphQL")]

"Started a research session. I'll capture our discussion
and any whiteboard diagrams. Ready when you are."

[During discussion]
Claude: [research_transcript_store for key points]
Claude: [research_capture_store for diagrams]

User: "Let's wrap up"

Claude: [research_session_end with summary and action items]

"Session saved to vault with transcript, captures, and
the key decisions we made. Action items:
1. Create GraphQL schema
2. Set up Apollo Server"
```

## Quality Indicators

### Good Memory Usage

- Relevant context surfaces naturally in responses
- User rarely needs to repeat themselves
- Sessions resume smoothly
- Memories are findable via search
- Relationships understood via knowledge graph
- Code easily located via livegrep

### Poor Memory Usage

- Frequently asking user to remind you
- Storing duplicate information
- Outdated preferences still surfacing
- Generic responses lacking project context
- Not using tier-specific tools when appropriate

## Tool Quick Reference

| Tool | Category | When to Use |
|------|----------|-------------|
| `memory_store` | Core | Learn something worth remembering |
| `memory_search` | Core | Before any context-dependent response |
| `memory_recall` | Core | Retrieve specific document by ID |
| `memory_delete` | Core | Remove outdated information |
| `memory_list` | Core | Orientation, overview of project |
| `session_save` | Core | Ending work, switching context |
| `session_restore` | Core | Starting session on known project |
| `vault_write` | Core | Permanent, human-readable docs |
| `vault_read` | Core | Read previously saved documentation |
| `memory_stats` | Core | Health checks, debugging |
| `search_entities` | Tier | Understanding entity relationships |
| `search_facts` | Tier | Finding facts between entities |
| `code_search` | Tier | RE2 regex code search |
| `search_function` | Tier | Find function definitions |
| `search_class` | Tier | Find class/struct definitions |
| `research_session_start` | Research | Begin voice/whiteboard session |
| `research_session_end` | Research | Complete session with summary |
| `research_transcript_store` | Research | Store voice transcript |
| `research_capture_store` | Research | Store whiteboard capture |
| `research_search` | Research | Search research data |

## Related Pages

- [[Memory-MCP]] - Overview
- [[Memory-MCP-Tools]] - Complete tool reference (all 20 tools)
- [[Memory-Tiers]] - Tier architecture with promotion logic
