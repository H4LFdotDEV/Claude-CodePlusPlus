# OpenClaw Integration

OpenClaw is a multi-channel AI gateway that provides access to Claude through messaging platforms like WhatsApp, Telegram, Discord, Slack, Signal, iMessage, and more.

When integrated with Claude Code++, OpenClaw shares the same Memory MCP server, enabling seamless context across all your interactions.

## Features

### Shared Memory

The key integration point is the `memory-mcp-bridge` extension. It connects OpenClaw to the same Memory MCP server used by Claude Code++:

```
┌─────────────────┐     ┌─────────────────┐
│  Claude Code    │     │    OpenClaw     │
│     CLI         │     │    Gateway      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │     Memory MCP        │
         │   (Shared across      │
         │    all clients)       │
         └───────────────────────┘
```

**Benefits:**
- Preferences set in terminal are available in WhatsApp
- Decisions made via Discord are remembered in Claude Code
- Research sessions can continue across devices
- Context follows you, not the interface

### Supported Channels

| Channel | Protocol | Setup |
|---------|----------|-------|
| WhatsApp | Baileys (web) / Twilio | QR code scan or API keys |
| Telegram | Bot API | Create bot via BotFather |
| Discord | Bot API | Discord application |
| Slack | Bolt SDK | Slack app installation |
| iMessage | BlueBubbles | macOS with BlueBubbles server |
| Signal | signal-cli | Signal account |
| Matrix | Matrix SDK | Matrix homeserver |
| Google Chat | Google Workspace | Service account |
| LINE | Messaging API | LINE developer account |

### Auto-Recall & Auto-Capture

The memory bridge provides two automatic behaviors:

**Auto-Recall:** Before each message, relevant memories are searched and injected into context:
```
User (WhatsApp): "How should I format this code?"
               ↓
OpenClaw: [searches memory for "code formatting"]
          → Finds: "User prefers tabs over spaces"
               ↓
Response: "I'll use tabs for indentation - that's your preference."
```

**Auto-Capture:** After conversations, important information is automatically stored:
- User preferences
- Decisions made
- Contact information mentioned
- Important facts

## Installation

### Via Unified Installer (Recommended)

```bash
cd Claude-CodePlusPlus
./install.sh
# Select "Yes" when asked about OpenClaw integration
```

### Manual Installation

```bash
# Install OpenClaw globally
npm install -g openclaw@latest

# Run onboarding wizard
openclaw onboard
```

### Configure Memory Bridge

The installer automatically configures the memory bridge. To verify or manually configure:

**~/.openclaw/openclaw.json:**
```json
{
  "plugins": {
    "memory-mcp-bridge": {
      "enabled": true,
      "mcpCommand": "~/.claude-code-pp/bin/memory-mcp",
      "autoRecall": true,
      "autoCapture": true,
      "recallLimit": 5,
      "recallMinScore": 0.3
    }
  }
}
```

## Configuration

### Basic Configuration

```bash
# Set API key
openclaw config set anthropic.apiKey sk-ant-...

# Configure gateway
openclaw config set gateway.port 18789
openclaw config set gateway.bind loopback
```

### Channel Configuration

Each channel is configured via `openclaw onboard` or `openclaw config set`:

**Telegram:**
```bash
openclaw config set telegram.botToken YOUR_BOT_TOKEN
```

**Discord:**
```bash
openclaw config set discord.botToken YOUR_BOT_TOKEN
```

**WhatsApp (Baileys):**
```bash
# Scan QR code during onboarding
openclaw onboard --channel whatsapp
```

**WhatsApp (Twilio):**
```bash
openclaw config set twilio.accountSid YOUR_SID
openclaw config set twilio.authToken YOUR_TOKEN
openclaw config set twilio.whatsappFrom whatsapp:+1234567890
```

## Running

### Start Gateway

```bash
# Start with configured channels
openclaw gateway run

# Start in background
openclaw daemon start
```

### Check Status

```bash
# Check all channels
openclaw channels status

# Check with probe (tests connectivity)
openclaw channels status --probe

# Check memory connection
openclaw memory stats
```

## Docker Deployment

OpenClaw can run as a Docker container alongside other Claude Code++ services:

```bash
# Start with OpenClaw
docker-compose -f docker/docker-compose.yaml --profile openclaw up -d
```

**docker-compose.yaml excerpt:**
```yaml
openclaw:
  container_name: claude-code-pp-openclaw
  profiles:
    - openclaw
  ports:
    - "127.0.0.1:18789:18789"
  environment:
    - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
    - OPENCLAW_PLUGIN_MEMORY_MCP_ENABLED=true
```

## Memory Bridge Configuration

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `mcpCommand` | `~/.claude-code-pp/bin/memory-mcp` | Path to Memory MCP binary |
| `mcpArgs` | `[]` | Arguments to pass to MCP command |
| `autoRecall` | `true` | Auto-inject relevant memories |
| `autoCapture` | `true` | Auto-store important info |
| `recallLimit` | `5` | Max memories to recall per query |
| `recallMinScore` | `0.3` | Minimum similarity for recall |

### Memory Categories

The bridge maps OpenClaw categories to Memory MCP types:

| OpenClaw | Memory MCP | Use Case |
|----------|------------|----------|
| preference | preference | "I prefer X over Y" |
| decision | decision | "We decided to use X" |
| entity | reference | Names, contacts, terms |
| fact | reference | "X is Y", "X has Y" |
| other | note | General information |

## CLI Commands

### Memory Commands

```bash
# List memories
openclaw memory list

# Search memories
openclaw memory search "authentication"

# Show statistics
openclaw memory stats
```

### Gateway Commands

```bash
# Run gateway
openclaw gateway run

# Run with specific port
openclaw gateway run --port 18789 --bind loopback

# Reset all connections
openclaw gateway run --reset
```

### Channel Commands

```bash
# Check channel status
openclaw channels status

# Send test message
openclaw message send --to "user@telegram" --text "Hello"
```

## Troubleshooting

### Memory Bridge Not Connecting

```bash
# Check if Memory MCP binary exists
ls -la ~/.claude-code-pp/bin/memory-mcp

# Test Memory MCP directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  ~/.claude-code-pp/bin/memory-mcp
```

### Gateway Not Starting

```bash
# Check for port conflicts
lsof -i :18789

# Check logs
openclaw daemon logs

# Reset and restart
openclaw gateway run --reset
```

### Channel Connection Issues

```bash
# Probe specific channel
openclaw channels status --probe

# Re-authenticate
openclaw onboard --channel <channel-name>
```

## Related Pages

- [[Memory-MCP]] - Memory system documentation
- [[Memory-MCP-Tools]] - Available memory tools
- [[Installation]] - Full installation guide
- [[Architecture]] - System architecture
