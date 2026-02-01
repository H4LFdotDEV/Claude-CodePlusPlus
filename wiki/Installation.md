# Installation

This guide covers installing Claude Code++ and its dependencies.

## Prerequisites

### Required
- **Claude Code CLI** - [Install from Anthropic](https://docs.anthropic.com/claude-code)
- **Python 3.10+** - For the Memory MCP server
- **Node.js 18+** - For npx-based MCP servers

### Optional (Recommended)
- **Redis** - Hot memory cache (significantly improves performance)
- **Docker** - For running infrastructure services

### Optional (Advanced)
- **Neo4j** - For Graphiti knowledge graph
- **Ollama** - For local LLM inference

## Quick Install

```bash
# Clone the repository
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus

# Run the installer
./install.sh
```

The installer will:
1. Create `~/.claude-code-pp/` directory structure
2. Install Python dependencies
3. Build the Memory MCP binary
4. Configure Claude Code to use the MCP servers

## Manual Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
```

### Step 2: Install Python Package

```bash
cd python
pip install -e ".[all]"
```

Install options:
- `pip install -e .` - Core only (SQLite, Vault)
- `pip install -e ".[redis]"` - Add Redis support
- `pip install -e ".[embeddings]"` - Add embedding support
- `pip install -e ".[all]"` - Everything

### Step 3: Create Directory Structure

```bash
mkdir -p ~/.claude-code-pp/{config,memory/{sqlite,vault},logs,cache}
```

### Step 4: Build Memory MCP Binary

```bash
cd python
python -m PyInstaller --onefile -n memory-mcp memory_mcp/server.py
cp dist/memory-mcp ~/.claude-code-pp/bin/
```

Or run directly with Python:
```bash
# Add to ~/.claude.json instead of binary path
"command": "python",
"args": ["-m", "memory_mcp.server"]
```

### Step 5: Configure Claude Code

Add to `~/.claude.json`:

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

Replace `YOUR_USERNAME` with your actual username.

## Installing Optional Services

### Redis (Recommended)

Redis provides the hot memory cache for sub-millisecond access to recent context.

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

**Verify:**
```bash
redis-cli ping
# Should return: PONG
```

### Docker Infrastructure

Start all optional services with Docker Compose:

```bash
cd docker
docker-compose up -d
```

This starts:
- Redis (port 6379) - Hot cache
- Neo4j (port 7474/7687) - Knowledge graph

With optional profiles:
```bash
# Include browser automation
docker-compose --profile browser up -d

# Include local LLM
docker-compose --profile local-llm up -d
```

### Neo4j (For Graphiti)

Graphiti requires Neo4j for the knowledge graph.

**Docker:**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Configure:**
Add to your environment or config:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Verifying Installation

### Check MCP Servers

```bash
# List configured MCP servers
claude --mcp-debug

# Test Memory MCP directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  ~/.claude-code-pp/bin/memory-mcp
```

### Check Memory Tools

Start Claude Code and run:
```
memory_stats
```

Should return component status and counts.

### Check Redis Connection

```bash
redis-cli ping
# PONG

redis-cli info memory | head -5
```

## Environment Variables

Optional environment variables for configuration:

```bash
# Memory MCP
export MEMORY_MCP_LOG_LEVEL=INFO
export MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/memory.log
export REDIS_URL=redis://localhost:6379
export OBSIDIAN_VAULT_PATH=~/Documents/Obsidian/Claude

# Embeddings
export VOYAGE_API_KEY=your-key-here  # For Voyage embeddings
export OPENAI_API_KEY=your-key-here  # For OpenAI embeddings

# Graphiti
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
```

## Updating

```bash
cd Claude-CodePlusPlus
git pull
cd python
pip install -e ".[all]"

# Rebuild binary if needed
python -m PyInstaller --onefile -n memory-mcp memory_mcp/server.py
cp dist/memory-mcp ~/.claude-code-pp/bin/
```

## Uninstalling

```bash
# Remove MCP configuration from ~/.claude.json
# Remove the mcpServers entries for "memory" and "prompts"

# Remove installation directory
rm -rf ~/.claude-code-pp

# Remove Python package
pip uninstall memory-mcp

# Stop Docker services (if used)
cd Claude-CodePlusPlus/docker
docker-compose down
```

## Next Steps

- [[Quick-Start]] - Get started in 5 minutes
- [[Configuration]] - Customize your setup
- [[Architecture]] - Understand how it works
