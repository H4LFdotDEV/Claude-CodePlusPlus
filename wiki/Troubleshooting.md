# Troubleshooting

Common issues and solutions for Claude Code++.

## Quick Diagnostics

### Check System Status

```bash
# Check Memory MCP
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  ~/.claude-code-pp/bin/memory-mcp

# Check Redis
redis-cli ping

# Check MCP servers in Claude
claude --mcp-debug
```

### Check from Claude

```
memory_stats
```

Returns component availability and health status.

## Common Issues

### Memory MCP Not Connecting

**Symptoms:**
- Memory tools not available in Claude
- "MCP server not found" errors

**Solutions:**

1. **Check MCP configuration:**
```bash
cat ~/.claude.json | jq '.mcpServers.memory'
```

2. **Verify binary exists:**
```bash
ls -la ~/.claude-code-pp/bin/memory-mcp
```

3. **Test server directly:**
```bash
~/.claude-code-pp/bin/memory-mcp --help
```

4. **Check logs:**
```bash
tail -f ~/.claude-code-pp/logs/memory.log
```

5. **Restart Claude Code:**
```bash
# Close and reopen terminal, or:
claude --mcp-debug
```

### Redis Connection Failed

**Symptoms:**
- `memory_stats` shows Redis unavailable
- Slow memory operations
- "ECONNREFUSED" errors in logs

**Solutions:**

1. **Check Redis is running:**
```bash
redis-cli ping
# Expected: PONG
```

2. **Start Redis:**
```bash
# macOS
brew services start redis

# Docker
docker run -d --name redis -p 6379:6379 redis:alpine

# Linux
sudo systemctl start redis
```

3. **Check connection URL:**
```bash
echo $REDIS_URL
# Should be: redis://localhost:6379
```

4. **Test connection:**
```bash
redis-cli -u redis://localhost:6379 ping
```

### Embeddings Not Working

**Symptoms:**
- Semantic search returns no results
- "Embedding provider unavailable" in stats

**Solutions:**

1. **Check provider configuration:**
```bash
echo $EMBEDDING_PROVIDER
echo $OPENAI_API_KEY  # If using OpenAI
echo $VOYAGE_API_KEY  # If using Voyage
```

2. **Use local embeddings:**
```bash
pip install sentence-transformers
export EMBEDDING_PROVIDER=local
```

3. **Check dependencies:**
```bash
pip install memory-mcp[embeddings]
```

### SQLite Database Locked

**Symptoms:**
- "database is locked" errors
- Operations hang

**Solutions:**

1. **Check for multiple processes:**
```bash
lsof ~/.claude-code-pp/memory/sqlite/memories.db
```

2. **Kill zombie processes:**
```bash
pkill -f memory-mcp
```

3. **Enable WAL mode (should be default):**
```bash
sqlite3 ~/.claude-code-pp/memory/sqlite/memories.db \
  "PRAGMA journal_mode=WAL;"
```

### Vault Write Failures

**Symptoms:**
- "Permission denied" on vault operations
- Files not appearing in vault

**Solutions:**

1. **Check vault path exists:**
```bash
ls -la ~/.claude-code-pp/memory/vault/
```

2. **Create vault structure:**
```bash
mkdir -p ~/.claude-code-pp/memory/vault/{code,notes,conversations,references,daily}
```

3. **Check permissions:**
```bash
chmod -R 755 ~/.claude-code-pp/memory/vault/
```

### Search Returns No Results

**Symptoms:**
- `memory_search` returns empty
- Known content not found

**Solutions:**

1. **Verify content exists:**
```bash
sqlite3 ~/.claude-code-pp/memory/sqlite/memories.db \
  "SELECT COUNT(*) FROM documents;"
```

2. **Try different search types:**
```json
// Text search (exact keywords)
{"query": "exact phrase", "type": "text"}

// Semantic search (conceptual)
{"query": "related concept", "type": "semantic"}

// Hybrid (both)
{"query": "search terms", "type": "hybrid"}
```

3. **Check filters:**
```json
// Remove restrictive filters
{"query": "search", "filters": {}}
```

4. **Rebuild FTS index:**
```bash
sqlite3 ~/.claude-code-pp/memory/sqlite/memories.db \
  "INSERT INTO documents_fts(documents_fts) VALUES('rebuild');"
```

### Session Restore Fails

**Symptoms:**
- `session_restore` returns nothing
- Previous sessions not found

**Solutions:**

1. **Check sessions exist:**
```bash
redis-cli KEYS "session:*"
```

2. **Without Redis, check SQLite:**
```bash
sqlite3 ~/.claude-code-pp/memory/sqlite/memories.db \
  "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 5;"
```

3. **Save a test session:**
```json
{
  "project_path": "/test",
  "active_files": ["test.txt"]
}
```

### High Memory Usage

**Symptoms:**
- Memory MCP using excessive RAM
- System slowdowns

**Solutions:**

1. **Limit Redis memory:**
```bash
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

2. **Vacuum SQLite:**
```bash
sqlite3 ~/.claude-code-pp/memory/sqlite/memories.db "VACUUM;"
```

### Slow Performance

**Symptoms:**
- Memory operations take seconds
- Noticeable lag in responses

**Solutions:**

1. **Enable Redis caching:**
   - Install and start Redis
   - Set `REDIS_URL` environment variable

2. **Check component latency:**
```
memory_stats
```
Look at `latency_ms` values in health section.

3. **Use text search for exact matches:**
```json
{"query": "exact error message", "type": "text"}
```

4. **Limit result counts:**
```json
{"query": "search", "limit": 5}
```

## Debug Mode

### Enable Verbose Logging

```bash
export MEMORY_MCP_LOG_LEVEL=DEBUG
export MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/debug.log
```

### Enable Request Tracing

```bash
export MEMORY_MCP_TRACE_ENABLED=true
export MEMORY_MCP_TRACE_FILE=~/.claude-code-pp/logs/trace.jsonl
```

### View Logs in Real-Time

```bash
tail -f ~/.claude-code-pp/logs/memory.log
```

## Reset and Recovery

### Reset Memory Database

**Warning:** This deletes all memories!

```bash
# Backup first
cp ~/.claude-code-pp/memory/sqlite/memories.db \
   ~/.claude-code-pp/memory/sqlite/memories.db.backup

# Reset
rm ~/.claude-code-pp/memory/sqlite/memories.db
```

### Reset Redis Cache

```bash
redis-cli FLUSHDB
```

### Full Reset

```bash
# Backup
cp -r ~/.claude-code-pp ~/.claude-code-pp.backup

# Reset
rm -rf ~/.claude-code-pp/memory/*
mkdir -p ~/.claude-code-pp/memory/{sqlite,vault}
```

## Getting Help

### Collect Diagnostic Information

```bash
# System info
echo "=== System ===" && uname -a

# Python version
echo "=== Python ===" && python --version

# Memory MCP version
echo "=== Memory MCP ===" && \
  ~/.claude-code-pp/bin/memory-mcp --version 2>/dev/null || echo "N/A"

# Redis status
echo "=== Redis ===" && redis-cli ping 2>/dev/null || echo "Not running"

# Recent logs
echo "=== Recent Logs ===" && \
  tail -20 ~/.claude-code-pp/logs/memory.log 2>/dev/null || echo "No logs"
```

### Report Issues

[GitHub Issues](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/issues)

Include:
- Error messages
- Steps to reproduce
- Diagnostic output (above)
- Claude Code version

## Related Pages

- [[Installation]] - Setup guide
- [[Configuration]] - Configuration options
- [[Architecture]] - System design
