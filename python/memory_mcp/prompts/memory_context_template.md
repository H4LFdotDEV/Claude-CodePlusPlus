# Memory Context Injection Template

This template defines how memory context is structured and injected into conversations when the pre-conversation hook detects relevant context.

---

## Template Structure

```markdown
## 📚 Your Memory Context for [PROJECT/TOPIC]

**Last Activity:** [timestamp - e.g., "2 days ago", "last session"]
**Session ID:** [restored_session_id if applicable]

### 🎯 Active Context
[Summary of what you were working on, current state, pending decisions]

### 💾 Key Memories
- [Recent decision]: [summary and reasoning]
- [User preference]: [what they prefer and why]
- [Technical constraint]: [what limits the approach]
- [Recent solution]: [if relevant to current work]

### 🛠️ Active Files/Components
- [file/module 1]: [purpose/state]
- [file/module 2]: [purpose/state]
- [feature X]: [status - in progress/completed/blocked]

### ⚠️ Known Issues
- [issue 1]: [status and workaround]
- [issue 2]: [status and workaround]

### 📋 Next Steps (From Last Session)
1. [Next task as noted]
2. [Pending decision]
3. [Blocked item - reason]

---
```

## Injection Points

The context above is injected:

1. **At conversation start** when:
   - User mentions a known project
   - User indicates work continuation
   - Session restoration was triggered
   - Pre-hook detects matching memories

2. **Before your first substantive response** to give you context

3. **Only when relevant** - don't inject if:
   - Starting entirely new project
   - User explicitly says "start fresh"
   - No matching session or memories found

## Component Descriptions

### Last Activity
- When this project/topic was last active
- Format: Human-readable ("2 days ago", "January 15", "last session")
- Purpose: Gives temporal context for how fresh/stale the context is

### Session ID
- Include only if session_restore was called
- Purpose: Reference for user to check session details
- Optional: Can be hidden if confusing

### Active Context
Short summary (1-3 sentences) of:
- What you were working on when the session ended
- Current state of implementation/work
- Major blockers or pending decisions

### Key Memories
Relevant memories retrieved from memory_search:
- Recent architectural decisions
- User preferences that apply to current work
- Project constraints
- Solutions to known problems
- Technology choices

**Limit**: Show 3-5 most relevant, not everything

### Active Files/Components
From session_restore if available:
- List of files the user was actively editing
- Components under development
- Feature status
- Modules under test

Helps orient you to the codebase quickly.

### Known Issues
Problems that were being worked on:
- Unresolved bugs
- Performance concerns
- Technical debt noted
- Workarounds in place

Prevents you from suggesting solutions that were tried/failed.

### Next Steps
From session notes or recent memories:
- Tasks noted as next
- Decisions that need to be made
- Blocked items waiting for input
- Research/exploration needed

Gives you immediate direction.

---

## Example: Rendered Context

```
## 📚 Your Memory Context for claude-code-pp

**Last Activity:** 1 day ago
**Session ID:** 28f3c2e1-9f4a-11eb-a8b3-0242ac130003

### 🎯 Active Context
You were implementing Phase 2.3.2 (tool schemas extraction). The validation.py extraction (Phase 2.3.1) was complete with 57 tests passing. Working on reducing server.py from 856 to 729 lines.

### 💾 Key Memories
- **Decision**: Use single-responsibility module extraction for server.py refactoring (prefer extraction to rewriting)
- **User Preference**: Always syntax-validate before committing
- **Constraint**: Must maintain MCP protocol compatibility - no breaking changes
- **Recent Discovery**: Pre-commit hooks are configured; use them for syntax validation

### 🛠️ Active Files/Components
- `python/memory_mcp/tool_schemas.py`: Created (181 lines)
- `python/tests/test_tool_schemas.py`: Created (391 lines, 29 tests)
- `python/memory_mcp/server.py`: Modified, reduced from 856 → 729 lines

### ⚠️ Known Issues
- None currently blocking progress

### 📋 Next Steps (From Last Session)
1. Complete Phase 2.3.2 commit
2. Begin Phase 2.3.3: Extract tool_handlers/ package
3. Target: 40 tests, ~370 lines to extract
```

---

## Usage in Conversation

When context is injected, use it to:

1. **Acknowledge awareness**: "I see from our last session that you were working on Phase 2.3.2..."
2. **Provide continuity**: "Let me continue the refactoring where we left off..."
3. **Reference constraints**: "Given the decision to maintain MCP compatibility..."
4. **Suggest next steps**: "Your next step was to extract tool_handlers..."
5. **Avoid repetition**: Don't re-explain preferences/decisions already stored

## When NOT to Inject Context

- User explicitly says "new project" or "start fresh"
- No matching session found
- Memories search returned nothing relevant
- User provides conflicting current context
- Starting work on a completely different topic

---

## Customization

Projects may have different context needs:

- **Software projects**: Focus on files, architecture, next tasks
- **Research/writing**: Focus on previous conclusions, sources, arguments
- **Creative work**: Focus on style decisions, themes, pending ideas
- **DevOps/Infrastructure**: Focus on deployment targets, constraints, automation status

Adjust template as needed for project type.

---

*Layer 3 of the Memory MCP System Prompt Architecture*
