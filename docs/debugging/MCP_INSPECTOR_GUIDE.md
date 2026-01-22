# MCP Inspector Integration Guide

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the official debugging tool for MCP servers. This guide covers using it with the Memory MCP Server.

## Overview

MCP Inspector provides:
- **Visual debugging UI** - React-based web interface
- **Protocol inspection** - View JSON-RPC requests/responses
- **Tool testing** - Interactive tool invocation
- **Real-time monitoring** - Watch server activity

## Quick Start

### Installation

```bash
# Launch directly with npx (no installation required)
npx @modelcontextprotocol/inspector python -m memory_mcp.server
```

Or use the provided startup script:

```bash
./scripts/start-inspector.sh
```

### Access the UI

Open http://localhost:6274 in your browser.

## Using MCP Inspector

### 1. Initial Connection

When you start the Inspector, it:
1. Launches the Memory MCP server as a subprocess
2. Connects via stdio
3. Calls `initialize` and `tools/list` automatically
4. Displays available tools in the sidebar

### 2. Testing Tools

#### memory_store

1. Select `memory_store` from the tool list
2. Fill in the arguments:
   ```json
   {
     "content": "def hello(): print('Hello!')",
     "type": "code",
     "source": "test.py",
     "tags": ["python", "test"],
     "project": "debug-session"
   }
   ```
3. Click "Execute"
4. View the response with the new document ID

#### memory_search

1. Select `memory_search`
2. Enter arguments:
   ```json
   {
     "query": "hello function",
     "type": "hybrid",
     "limit": 10
   }
   ```
3. Execute and review search results

#### memory_stats

1. Select `memory_stats`
2. No arguments needed - just execute
3. Review:
   - Component availability
   - Health status with latencies
   - Document counts

### 3. Debugging Scenarios

#### Verify Component Health

1. Run `memory_stats`
2. Check the `health` section:
   ```json
   {
     "health": {
       "sqlite": { "status": "healthy", "latency_ms": 0.5 },
       "vault": { "status": "connected", "latency_ms": 1.2 },
       "redis": { "status": "not_available" },
       "faiss": { "status": "available", "latency_ms": 0.8 },
       "embedder": { "status": "active" }
     }
   }
   ```

#### Test Search Types

Compare search results across different types:

1. **Text search**: `{"query": "print", "type": "text"}`
2. **Semantic search**: `{"query": "function that outputs greeting", "type": "semantic"}`
3. **Hybrid search**: `{"query": "hello world", "type": "hybrid"}`

#### Session Management Flow

1. Save a session:
   ```json
   {
     "project_path": "/test/project",
     "active_files": ["main.py"],
     "context": {"task": "testing"}
   }
   ```
2. Note the `session_id` from response
3. Restore it:
   ```json
   {
     "session_id": "<id-from-above>"
   }
   ```

### 4. Viewing Protocol Messages

The Inspector shows:
- **Request** - JSON-RPC request sent to server
- **Response** - Server's JSON-RPC response
- **Timing** - Request duration
- **Errors** - Any error messages

Example request/response pair:

```
→ Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "memory_stats",
    "arguments": {}
  }
}

← Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"sqlite_count\": 42, ...}"
      }
    ]
  }
}
```

## Configuration

### Environment Variables

Set before starting the Inspector:

```bash
# Enable debug logging
export MEMORY_MCP_LOG_LEVEL=DEBUG
export MEMORY_MCP_LOG_FILE=/tmp/memory-mcp.log

# Configure components
export REDIS_URL=redis://localhost:6379
export OBSIDIAN_VAULT_PATH=~/.obsidian/vault

# Start inspector
npx @modelcontextprotocol/inspector python -m memory_mcp.server
```

### Custom Port

```bash
# Use different port
npx @modelcontextprotocol/inspector --port 8080 python -m memory_mcp.server
```

## Troubleshooting

### Inspector Won't Start

**Symptom**: Error on launch

**Solutions**:
1. Check Node.js version (requires v18+)
2. Verify Python environment has memory_mcp installed
3. Check for port conflicts on 6274

### Server Crashes on Tool Call

**Symptom**: Connection lost after tool execution

**Debug steps**:
1. Enable debug logging: `MEMORY_MCP_LOG_LEVEL=DEBUG`
2. Check log file for stack trace
3. Run `python -m memory_mcp.diagnostics` for health check

### Empty Search Results

**Symptom**: Searches return no results

**Check**:
1. Run `memory_stats` - verify `sqlite_count` > 0
2. Verify FAISS is available for semantic search
3. Check embedder status for vector search

### Redis/FAISS Not Available

**Symptom**: Components show "not_available" in stats

**This is normal** if:
- Redis server isn't running (optional component)
- FAISS isn't installed (optional component)

**To enable**:
```bash
# Start Redis
docker run -d -p 6379:6379 redis

# Install FAISS
pip install faiss-cpu
```

## Integration with Development Workflow

### 1. Pre-commit Testing

Before committing changes to Memory MCP:
1. Start Inspector
2. Run through basic CRUD flow
3. Verify all 10 tools respond correctly

### 2. Debugging Production Issues

1. Replicate the issue parameters
2. Use Inspector to test the exact tool call
3. Check response for error details
4. Review server logs

### 3. Performance Analysis

Use `memory_stats` health section to monitor:
- Component latencies
- Cache hit ratios (Redis)
- Vector counts (FAISS)

## Related Tools

### CLI Debug Client

For command-line debugging:
```bash
python -m memory_mcp.cli_debug
> stats
> search "hello"
> health
```

### Component Diagnostics

Quick health check:
```bash
python -m memory_mcp.diagnostics
```

### Bruno Collection

API testing with Bruno:
```bash
cd bruno/memory-mcp
bruno run --env local
```

## Resources

- [MCP Inspector GitHub](https://github.com/modelcontextprotocol/inspector)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Memory MCP README](../../python/README.md)
- [Bruno Collection](../../bruno/memory-mcp/README.md)
