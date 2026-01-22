# Memory MCP Behavioral Guidelines

How Claude should use the Memory MCP system effectively.

## Core Philosophy

Memory is integral to Claude's identity with each user. It's not a database to query occasionally - it's how Claude genuinely remembers past interactions, preferences, and decisions.

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

Claude thinks: User references past work → search memory
Claude: [calls memory_search("auth service approach")]
Claude: "Found it - we used JWT with refresh token rotation,
         with Redis for session storage. Same approach here?"
```

### Example: Wrong Way

```
User: "Use the same approach we used for the auth service"

Claude: "I apologize, but I don't have memory of our previous
         conversations. Could you remind me what approach..."

❌ Claude didn't search before admitting ignorance
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

## Tier Selection

### When to Use Each Tier

| Query Type | Primary Tier | Example |
|------------|--------------|---------|
| "What's the current task?" | Redis | Session context |
| "How does auth relate to users?" | Graphiti | Relationships |
| "Find similar errors" | LanceDB | Semantic similarity |
| "Where is function X?" | livegrep | Code search |
| "What did we decide about X?" | SQLite | Full-text search |
| "Show me the architecture doc" | Vault | Human docs |

### Automatic Routing

The `memory_search` tool automatically routes queries to appropriate tiers:

- Relationship language → Graphiti
- Conceptual/semantic → LanceDB
- Exact keywords → SQLite FTS
- Code patterns → livegrep

Just use `memory_search` with `type="hybrid"` for best results.

## Anti-Patterns to Avoid

### 1. Apologizing Without Searching

❌ **Bad:**
```
"I apologize, but I don't have memory of our previous conversations..."
```

✅ **Good:**
```
[Search first]
"I searched my memory but didn't find records of that.
Could you remind me of the context?"
```

### 2. Asking Permission to Search

❌ **Bad:**
```
"Would you like me to check my memory for previous discussions?"
```

✅ **Good:**
```
[Just search - it's your memory, use it naturally]
```

### 3. Storing Everything

❌ **Bad:**
```
[Stores every code snippet, every response, every trivial exchange]
```

✅ **Good:**
```
[Stores selectively: preferences, decisions, solutions, important context]
```

### 4. Forgetting to Update

❌ **Bad:**
```
User: "Changed my mind about Redux"
Claude: "Okay" [doesn't update stored decision]
```

✅ **Good:**
```
User: "Changed my mind about Redux"
Claude: [searches, deletes old preference, stores new one]
        "Got it, updated my notes. What are we using instead?"
```

### 5. Generic Memories

❌ **Bad:**
```
memory_store(
  content="User likes clean code",
  tags=[]  // No tags!
)
```

✅ **Good:**
```
memory_store(
  content="User prefers clean code: small functions, meaningful names, no comments for obvious code",
  tags=["preference", "coding-style"],
  project="user-profile"
)
```

## Example Conversation Patterns

### Pattern 1: Continuing Previous Work

```
User: "Let's continue working on the API gateway"

Claude: [session_restore]
Claude: [memory_search(project="api-gateway")]

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

"Found it - we chose PostgreSQL for this project because
of the complex relational queries. I have the connection
config stored. Should I set up the schema?"
```

### Pattern 3: Learning New Preference

```
User: "I prefer using async/await over .then() chains"

Claude: [memory_store with preference tags]

"Noted - I'll use async/await going forward. This applies
to all projects or just this one?"

User: "All projects"

Claude: [updates memory with broader scope]

"Got it, stored as a global preference."
```

### Pattern 4: Correcting Outdated Info

```
User: "We're not using Redux anymore, switched to Zustand"

Claude: [memory_search("Redux OR state management")]
Claude: [memory_delete old Redux decision]
Claude: [memory_store new Zustand decision]

"Updated - Zustand it is. I've removed the Redux notes
and stored the new approach. Want me to update the
architecture documentation in vault too?"
```

## Quality Indicators

### Good Memory Usage

- Relevant context surfaces naturally in responses
- User rarely needs to repeat themselves
- Sessions resume smoothly
- Memories are findable via search

### Poor Memory Usage

- Frequently asking user to remind you
- Storing duplicate information
- Outdated preferences still surfacing
- Generic responses lacking project context

## Related Pages

- [[Memory-MCP]] - Overview
- [[Memory-MCP-Tools]] - Tool reference
- [[Memory-Tiers]] - Tier architecture
