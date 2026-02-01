# Quick Start

Get running with Claude Code++ in under 5 minutes.

## Option A: One-Liner Install (Fastest)

```bash
curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/quick-install.sh | bash
```

For fully automated with all defaults:

```bash
curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/quick-install.sh | bash -s -- --quick
```

## Option B: Clone and Install

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
./install.sh              # Interactive mode
./install.sh --quick      # All defaults, no prompts
./install.sh --help       # See all options
```

The installer will guide you through:
- Choosing an installation profile
- Setting up Docker services
- Optional: OpenClaw multi-channel gateway
- Optional: Research environment (voice + webcam)

## Step 2: Verify

Open Claude Code and run:

```
memory_stats
```

You should see component status. At minimum, `sqlite` and `vault` should be `true`.

## Step 3: Store Your First Memory

Tell Claude to remember something:

```
"Remember that I prefer TypeScript over JavaScript for this project"
```

Or use the tool directly:

```
memory_store(
  content="Prefers TypeScript over JavaScript",
  type="preference",
  tags=["language", "project"]
)
```

## Step 4: Search Memory

Later, when you need that context:

```
memory_search(query="TypeScript preference")
```

Or just ask naturally - Claude will search automatically when you reference past decisions.

## Step 5: Save Session

Before ending your session:

```
session_save(project_path="/path/to/your/project")
```

This saves:
- Active files you were working on
- Recent memories accessed
- Custom context (tasks, decisions)

## Step 6: Restore Session

Next time you start:

```
session_restore
```

Claude picks up exactly where you left off.

## You're Ready!

Claude now has persistent memory. Key behaviors:

1. **Auto-search**: Claude searches memory when you reference past work
2. **Auto-store**: Important info is captured for future sessions
3. **Session continuity**: Pick up where you left off

## Optional: OpenClaw Setup

If you enabled OpenClaw during installation, configure your channels:

```bash
# Configure Telegram
openclaw config set telegram.botToken YOUR_TOKEN

# Configure Discord
openclaw config set discord.botToken YOUR_TOKEN

# Or use the interactive wizard
openclaw onboard
```

Start the gateway:

```bash
openclaw gateway run
```

Now you can chat with Claude (with your memory) via WhatsApp, Telegram, Discord, etc.

## Quick Reference

### Memory Tools

| Tool | Purpose |
|------|---------|
| `memory_search` | Find relevant context |
| `memory_store` | Save important info |
| `memory_list` | Browse memories |
| `memory_recall` | Get specific memory by ID |
| `memory_delete` | Remove a memory |

### Session Tools

| Tool | Purpose |
|------|---------|
| `session_save` | Save working state |
| `session_restore` | Resume previous session |

### Research Tools

| Tool | Purpose |
|------|---------|
| `research_session_start` | Start voice/whiteboard session |
| `research_session_end` | End and summarize session |
| `research_search` | Search research data |

### Knowledge Graph Tools

| Tool | Purpose |
|------|---------|
| `search_entities` | Find entities in knowledge graph |
| `search_facts` | Find relationships |
| `code_search` | Search code across repos |

### System Tools

| Tool | Purpose |
|------|---------|
| `memory_stats` | Check system health |
| `vault_write` | Write to Obsidian vault |
| `vault_read` | Read from vault |

## Example Workflows

### Starting a New Project

```
# Tell Claude about project preferences
"This is a React project. We're using TypeScript, Tailwind CSS,
 and Zustand for state management. I prefer functional components."

# Claude stores these as preferences
# Later references will recall them automatically
```

### Resuming Work

```
# Restore session
session_restore

# Claude knows where you left off
"Continue from yesterday"
# → "We were implementing the auth flow using JWT..."
```

### Cross-Channel Continuity

In terminal:
```
"I prefer tabs over spaces"
# Stored in memory
```

Later, in WhatsApp (via OpenClaw):
```
"Format this code"
# OpenClaw recalls preference, uses tabs
```

## Troubleshooting

### MCP Not Connecting

```bash
# Check if Memory MCP is configured
claude --mcp-debug

# Test Memory MCP directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  ~/.claude-code-pp/bin/memory-mcp
```

### Redis Not Available

Redis is optional. Without it:
- Hot cache is disabled
- Session access is slower
- Everything else works fine

### OpenClaw Not Starting

```bash
# Check status
openclaw channels status --probe

# Check logs
openclaw daemon logs
```

## Next Steps

- [[Memory-MCP]] - Learn about the memory system
- [[Memory-MCP-Behavioral-Guidelines]] - How Claude uses memory
- [[OpenClaw]] - Set up multi-channel access
- [[Research-Environment]] - Voice + webcam research mode
- [[Configuration]] - Customize your setup
