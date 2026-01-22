# Quick Start

Get running with Claude Code++ in 5 minutes.

## Prerequisites

- Claude Code CLI installed
- Python 3.10+

## Step 1: Clone and Install

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
./install.sh
```

## Step 2: (Optional) Start Redis

Redis significantly improves performance but isn't required.

```bash
# macOS
brew install redis && brew services start redis

# Or Docker
docker run -d --name redis -p 6379:6379 redis:alpine
```

## Step 3: Verify Installation

Open Claude Code and run:

```
memory_stats
```

You should see component status. At minimum, `sqlite` and `vault` should be `true`.

## Step 4: Store Your First Memory

```
memory_store(
  content="My first memory!",
  type="note",
  source="quick-start"
)
```

## Step 5: Search Memory

```
memory_search(query="first memory")
```

## Step 6: Save Session

Before ending:

```
session_save(project_path="/path/to/your/project")
```

## Step 7: Restore Session

Next time you start:

```
session_restore
```

## You're Ready!

Claude now has persistent memory. Key behaviors to know:

1. **Claude searches memory automatically** when you reference past work
2. **Important info is stored** for future sessions
3. **Sessions persist** - pick up where you left off

## Next Steps

- [[Memory-MCP]] - Learn about the memory system
- [[Memory-MCP-Behavioral-Guidelines]] - How Claude uses memory
- [[Configuration]] - Customize your setup

## Quick Reference

| Tool | Purpose |
|------|---------|
| `memory_search` | Find relevant context |
| `memory_store` | Save important info |
| `memory_list` | Browse recent memories |
| `session_save` | Save working state |
| `session_restore` | Resume previous session |
| `memory_stats` | Check system health |
