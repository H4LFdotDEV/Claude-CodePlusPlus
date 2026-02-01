# Memory MCP Bruno Collection

API testing collection for the Memory MCP Server using [Bruno](https://www.usebruno.com/).

## Overview

This collection provides test requests for all 10 Memory MCP tools:

| Tool | Description | File |
|------|-------------|------|
| memory_store | Store content in long-term memory | Store Memory.bru |
| memory_search | Search using text/semantic similarity | Search Memory.bru |
| memory_recall | Recall specific memory by ID | Recall Memory.bru |
| memory_delete | Delete a memory | Delete Memory.bru |
| memory_list | List recent memories | List Memories.bru |
| session_save | Save session state | Save Session.bru |
| session_restore | Restore previous session | Restore Session.bru |
| vault_write | Write to Obsidian vault | Write to Vault.bru |
| vault_read | Read from Obsidian vault | Read from Vault.bru |
| memory_stats | Get system statistics | Memory Stats.bru |

## Setup

### 1. Install Bruno CLI

```bash
npm install -g @usebruno/cli
```

### 2. Start the Memory MCP HTTP Bridge

Since Memory MCP uses stdio, you'll need an HTTP bridge for Bruno testing:

```bash
# Use the MCP Inspector (recommended)
npx @modelcontextprotocol/inspector python -m memory_mcp.server
```

This opens an inspector UI at http://localhost:5173 with an MCP endpoint for testing.

### 3. Configure Environment

The `environments/local.bru` file contains:
- `base_url`: http://localhost:8080
- `mcp_endpoint`: /mcp

Update these values if your setup differs.

## Running Tests

### Run All Tests
```bash
cd bruno/memory-mcp
bruno run --env local
```

### Run Specific Test
```bash
bruno run "Store Memory.bru" --env local
```

### Run with Output
```bash
bruno run --env local --output results.json
```

## Request Format

All requests use the MCP JSON-RPC format:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": { ... }
  }
}
```

## Response Format

Successful responses:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{ \"key\": \"value\" }"
      }
    ]
  }
}
```

Error responses:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "isError": true,
    "content": [
      {
        "type": "text",
        "text": "Error message"
      }
    ]
  }
}
```

## Test Scenarios

### Basic CRUD Flow
1. Store Memory.bru - Create a memory
2. Memory Stats.bru - Verify it was stored
3. Search Memory.bru - Find it by content
4. Recall Memory.bru - Get full details
5. Delete Memory.bru - Remove it
6. Memory Stats.bru - Verify deletion

### Session Flow
1. Save Session.bru - Save current state
2. Restore Session.bru - Restore the session
3. Memory Stats.bru - Verify session ID

### Vault Flow
1. Write to Vault.bru - Create a note
2. Read from Vault.bru - Retrieve the note

## Assertions

Each request includes assertions to verify:
- HTTP status code (200)
- No error in response (`isError` is undefined)
- Expected fields in response

## Integration with CI/CD

```yaml
# GitHub Actions example
- name: Run Memory MCP API Tests
  run: |
    npm install -g @usebruno/cli
    bruno run bruno/memory-mcp --env local --output test-results.json
```

## Troubleshooting

### Connection Refused
- Ensure the HTTP bridge is running
- Check the port configuration

### Invalid Response
- Verify the MCP server is started correctly
- Check server logs for errors

### Assertion Failures
- Review the response body in Bruno
- Check the Memory MCP logs for errors

## Related Resources

- [Bruno Documentation](https://docs.usebruno.com/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Memory MCP Server Documentation](../../python/README.md)
