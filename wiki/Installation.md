# Installation

This guide covers installing Claude Code++ and all its components.

## Unified Installer (Recommended)

The easiest way to install Claude Code++ is with the unified installer:

```bash
# Clone the repository
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus

# Run the installer
./install.sh
```

The installer will:
1. **Detect your system resources** and recommend an installation profile
2. **Create directory structure** at `~/.claude-code-pp/`
3. **Install Memory MCP** server with tiered storage
4. **Start Docker services** (Redis, Neo4j based on profile)
5. **Configure Claude Code** to use the MCP servers
6. **Install OpenClaw** (optional) for multi-channel access
7. **Set up Research Environment** (optional) for voice + webcam

**Total time: ~5 minutes** (excluding Docker image pulls)

## Prerequisites

### Required
- **Claude Code CLI** - [Install from Anthropic](https://docs.anthropic.com/claude-code)
- **Python 3.10+** - For the Memory MCP server
- **Node.js 22+** - For OpenClaw (if enabled)

### Recommended
- **Docker** - For Redis, Neo4j, and other services
- **Redis** - Hot memory cache (significantly improves performance)

### Optional
- **Neo4j** - For Graphiti knowledge graph
- **Ollama** - For local LLM inference

## Installation Profiles

The installer detects your system and recommends a profile:

| Profile | Components | RAM | Use Case |
|---------|------------|-----|----------|
| **minimal** | SQLite + Vault | 2GB | Low-resource systems |
| **standard** | + Redis | 4GB | Most users (recommended) |
| **full** | + Neo4j/Graphiti | 8GB | Knowledge graph queries |
| **enterprise** | + livegrep | 16GB | Cross-repo code search |

## What Gets Installed

### Directory Structure

```
~/.claude-code-pp/
├── bin/
│   └── memory-mcp          # MCP server binary
├── config/
│   └── settings.yaml       # Main configuration
├── memory/
│   ├── sqlite/             # Metadata database
│   └── vault/              # Obsidian-compatible notes
├── logs/
│   └── memory.log          # Server logs
├── cache/
└── venv/                   # Python virtual environment
```

### Claude Code Configuration

The installer adds to `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "/Users/YOUR_USERNAME/.claude-code-pp/bin/memory-mcp",
      "args": []
    },
    "prompts": {
      "command": "npx",
      "args": ["-y", "prompts.chat", "mcp"]
    }
  }
}
```

### OpenClaw Configuration (Optional)

If OpenClaw is installed, configuration is at `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "memory-mcp-bridge": {
      "enabled": true,
      "mcpCommand": "~/.claude-code-pp/bin/memory-mcp"
    }
  }
}
```

## Manual Installation

If you prefer manual setup:

### Step 1: Clone Repository

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
```

### Step 2: Create Directory Structure

```bash
mkdir -p ~/.claude-code-pp/{bin,config,memory/{sqlite,vault},logs,cache}
```

### Step 3: Install Python Package

```bash
cd python
python3 -m venv ~/.claude-code-pp/venv
source ~/.claude-code-pp/venv/bin/activate
pip install -e ".[all]"
```

Install options:
- `pip install -e .` - Core only (SQLite, Vault)
- `pip install -e ".[redis]"` - Add Redis support
- `pip install -e ".[all]"` - Everything

### Step 4: Create MCP Wrapper

```bash
cat > ~/.claude-code-pp/bin/memory-mcp << 'EOF'
#!/bin/bash
source ~/.claude-code-pp/venv/bin/activate
exec python -m memory_mcp "$@"
EOF
chmod +x ~/.claude-code-pp/bin/memory-mcp
```

### Step 5: Configure Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "/Users/YOUR_USERNAME/.claude-code-pp/bin/memory-mcp",
      "args": []
    }
  }
}
```

### Step 6: Start Docker Services (Optional)

```bash
cd docker
docker-compose up -d
```

## Installing Optional Components

### Redis (Recommended)

Redis provides the hot memory cache for sub-millisecond access.

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

### Neo4j (For Graphiti)

Graphiti requires Neo4j for the knowledge graph.

**Docker (Recommended):**
```bash
docker-compose -f docker/docker-compose.yaml up -d neo4j
```

**Or standalone:**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5-community
```

### OpenClaw (Multi-Channel Gateway)

```bash
# Install globally
npm install -g openclaw@latest

# Configure
openclaw onboard
```

See [[OpenClaw]] for full setup instructions.

### Research Environment

```bash
./scripts/setup-research-env.sh
```

This installs:
- VoiceMode for voice conversations
- mcp-webcam for whiteboard capture

See [[Research-Environment]] for details.

## Verifying Installation

### Check MCP Servers

```bash
# List configured MCP servers
claude --mcp-debug
```

### Test Memory MCP

```bash
# Direct test
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  ~/.claude-code-pp/bin/memory-mcp
```

### Check Memory Tools

In Claude Code, run:
```
memory_stats
```

Should return component status for all tiers.

### Check Redis

```bash
redis-cli ping
# Should return: PONG
```

### Check OpenClaw

```bash
openclaw channels status
openclaw memory stats
```

## Environment Variables

Optional environment variables:

```bash
# Memory MCP
export MEMORY_MCP_LOG_LEVEL=INFO
export MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/memory.log
export REDIS_URL=redis://localhost:6379
export OBSIDIAN_VAULT_PATH=~/Documents/Obsidian/Claude

# Graphiti
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password

# Optional embeddings
export VOYAGE_API_KEY=your-key
export OPENAI_API_KEY=your-key
```

## Updating

```bash
cd Claude-CodePlusPlus
git pull

# Re-run installer
./install.sh
```

Or manually:

```bash
cd python
source ~/.claude-code-pp/venv/bin/activate
pip install -e ".[all]"
```

## Uninstalling

```bash
# Remove MCP configuration from ~/.claude.json
# (remove the "memory" entry from mcpServers)

# Remove installation directory
rm -rf ~/.claude-code-pp

# Stop Docker services
cd Claude-CodePlusPlus/docker
docker-compose down

# Remove OpenClaw (if installed)
npm uninstall -g openclaw
rm -rf ~/.openclaw
```

## Next Steps

- [[Quick-Start]] - Get started in 5 minutes
- [[Configuration]] - Customize your setup
- [[OpenClaw]] - Set up multi-channel access
- [[Architecture]] - Understand how it works
