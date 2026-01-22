# Memory MCP: API Health Verification & Debug Suite Implementation Plan

## Overview

Create comprehensive API health verification, debugging tools, and GUI testing infrastructure for the Memory MCP server. This plan addresses three tiers: **immediate** (health + debug), **short-term** (Bruno/MCP Inspector integration), and **future** (custom GUI + IDE integration).

---

## Background Context

### Current State
- **10 MCP tools**: memory_store, memory_search, memory_recall, memory_delete, memory_list, session_save, session_restore, vault_write, vault_read, memory_stats
- **402 existing tests** across 17 test files (8,434 lines)
- **Tiered memory architecture**: Redis (hot) → FAISS (warm) → SQLite/Vault (cold)
- **Test patterns established**: Class-based pytest, fixture reuse via conftest.py, graceful degradation testing

### Research Findings

**Testing Infrastructure (Agent ab1d6c5)**:
- Strong patterns: Class-based organization, comprehensive fixtures
- **Gaps**: Limited error scenario coverage, no comprehensive health verification

**Debug/Diagnostic Tooling (Agent a3b4df2)**:
- **Pain points**: No MCP protocol inspection, no memory tier visibility
- **Priority needs**: CLI debug client > enhanced stats > request tracing

**GUI/API Testing Ecosystem (Agent a28bb49)**:
- **Bruno**: Open-source Postman alternative, plain text .bru format, IDE extensions exist
- **MCP Inspector**: Official debugging tool with React web UI + Node.js proxy

---

## Phase 2.6: API Health Verification Suite (Immediate)

**Goal**: Verify all 10 MCP endpoints are operational and components are healthy.

**File**: `python/tests/test_api_health.py` (~450 lines, 25 tests)

### Test Categories

| Category | Tests | Description |
|----------|-------|-------------|
| Endpoint Availability | 10 | One test per MCP tool verifying response structure |
| Component Health | 5 | Redis, FAISS, SQLite, Vault, Embedder connectivity |
| Graceful Degradation | 5 | System works when optional components unavailable |
| Concurrent Access | 3 | Thread-safe operations under load |
| Performance Baseline | 2 | Latency targets (<100ms store, <50ms search) |

### Implementation Pattern
```python
class TestAPIHealth:
    """API health verification tests."""

    def test_memory_store_available(self, test_config, mock_redis):
        # Test store endpoint responds
        # Verify response structure
        # Confirm no exceptions
        pass

    def test_redis_health_when_unavailable(self, test_config):
        # Patch REDIS_AVAILABLE to False
        # Verify session_save falls back to SQLite
        pass
```

**Dependencies**: Reuse fixtures from conftest.py (test_config, mock_redis, mock_faiss)

---

## Phase 2.7: Full Debug Suite (Immediate)

### 2.7.1: CLI Debug Client

**File**: `python/memory_mcp/cli_debug.py` (~300 lines)

**Features**:
- Interactive REPL for invoking MCP tools
- Pretty-printed JSON responses
- Request/response timing
- Error traceback display

**Commands**:
```bash
python -m memory_mcp.cli_debug
> store "Test content" note test-source --tags test
> search "Test" --type hybrid --limit 10
> stats
> health
> help
```

**Test File**: `python/tests/test_cli_debug.py` (~200 lines, 10 tests)

---

### 2.7.2: Enhanced Memory Stats

**File to Modify**: `python/memory_mcp/server.py` (memory_stats handler)

**New Response Format**:
```json
{
  "sqlite_count": 1523,
  "components": { "redis": true, "faiss": true, "sqlite": true },
  "redis": {
    "cache_hits": 1234,
    "cache_misses": 56,
    "hit_ratio": 0.957,
    "memory_usage_bytes": 1048576
  },
  "faiss": {
    "total_vectors": 5420,
    "dimension": 768,
    "index_type": "flat"
  },
  "health": {
    "redis": { "status": "healthy", "latency_ms": 0.8 },
    "faiss": { "status": "available" },
    "sqlite": { "status": "connected" }
  }
}
```

**Test File**: `python/tests/test_enhanced_stats.py` (~150 lines, 8 tests)

---

### 2.7.3: Request Tracing System

**File**: `python/memory_mcp/request_tracer.py` (~250 lines)

**Features**:
- Assign request_id to every MCP tool invocation
- Log request/response/error with timestamps
- Track request flow through memory tiers
- Performance profiling per request

**Integration**: Decorator pattern for tool handlers
```python
@trace_request
async def handle_memory_store(arguments: dict) -> dict:
    # Existing logic with automatic tracing
    pass
```

**Test File**: `python/tests/test_request_tracer.py` (~200 lines, 10 tests)

---

### 2.7.4: Component Diagnostics

**File**: `python/memory_mcp/diagnostics.py` (~200 lines)

**Features**:
- Check Redis/FAISS/SQLite/Vault/Embedder connectivity
- Detailed error messages with fix suggestions
- CLI entry point: `python -m memory_mcp.diagnostics`

**Test File**: `python/tests/test_diagnostics.py` (~150 lines, 8 tests)

---

## Phase 2.8: Bruno Collection (Short-term)

**Goal**: Create regression test suite using Bruno's plain-text format.

**Directory**: `bruno/memory-mcp/`

**Files** (~15 .bru files):
- `Store Memory.bru` - memory_store test cases
- `Search Memory.bru` - memory_search with text/semantic/hybrid
- `Recall Memory.bru` - memory_recall with valid/invalid IDs
- `Delete Memory.bru` - memory_delete test cases
- `List Memories.bru` - memory_list with filters
- `Save Session.bru` - session_save test cases
- `Restore Session.bru` - session_restore test cases
- `Write to Vault.bru` - vault_write test cases
- `Read from Vault.bru` - vault_read test cases
- `Memory Stats.bru` - memory_stats test cases

**Example .bru file**:
```bru
meta {
  name: Store Memory - Valid Code
  type: http
  seq: 1
}

post {
  url: {{base_url}}/mcp/memory_store
  body: json
}

body:json {
  {
    "content": "def hello(): print('Hello')",
    "type": "code",
    "source": "example.py",
    "tags": ["python"],
    "project": "test-project"
  }
}

tests {
  test("Status code is 200", function() {
    expect(res.status).to.equal(200);
  });
}
```

**CI/CD**: `bruno run bruno/memory-mcp --env local`

---

## Phase 2.9: MCP Inspector Integration (Short-term)

**Goal**: Document how to use MCP Inspector for visual debugging.

**File**: `docs/debugging/MCP_INSPECTOR_GUIDE.md` (~200 lines)

**Content**:
1. Installation: `npx @modelcontextprotocol/inspector python -m memory_mcp.server`
2. Usage guide for testing all 10 tools
3. Debugging scenarios (component health, error handling, performance)
4. Integration with development workflow

**Startup Script**: `scripts/start-inspector.sh`
```bash
#!/bin/bash
npx @modelcontextprotocol/inspector python -m memory_mcp.server
```

---

## Phase 2.10+: Future GUI Roadmap (Documented Only)

**Goal**: Custom GUI combining Bruno + MCP Inspector + Memory visualization

**Architecture**:
```
React Web UI (Port 3000)
  ├── API Testing Panel (Bruno-inspired)
  ├── MCP Protocol Viewer (Inspector-inspired)
  ├── Memory Tier Visualization
  └── Session Manager
         │
    MCP Proxy Server (Node.js)
         │
    Memory MCP Server (Python)
```

**IDE Integration**: Follow Bruno IDE extension pattern (https://github.com/usebruno/bruno-ide-extensions)

**Timeline**: 12-16 weeks when ready to implement

---

## Critical Files Summary

### Immediate (Phases 2.6-2.7)

| File | Lines | Tests | Purpose |
|------|-------|-------|---------|
| `python/tests/test_api_health.py` | ~450 | 25 | Health verification suite |
| `python/memory_mcp/cli_debug.py` | ~300 | - | CLI debug client |
| `python/tests/test_cli_debug.py` | ~200 | 10 | CLI tests |
| `python/tests/test_enhanced_stats.py` | ~150 | 8 | Enhanced stats tests |
| `python/memory_mcp/request_tracer.py` | ~250 | - | Request tracing |
| `python/tests/test_request_tracer.py` | ~200 | 10 | Tracer tests |
| `python/memory_mcp/diagnostics.py` | ~200 | - | Component diagnostics |
| `python/tests/test_diagnostics.py` | ~150 | 8 | Diagnostics tests |
| `python/memory_mcp/server.py` | ~50 mod | - | Enhanced memory_stats |

**Total**: ~1,950 lines code + ~700 lines tests = **2,650 lines**, **71 new tests**

### Short-term (Phases 2.8-2.9)

| File | Lines | Purpose |
|------|-------|---------|
| `bruno/memory-mcp/*.bru` | ~450 | 15 Bruno test files |
| `bruno/memory-mcp/README.md` | ~100 | Collection docs |
| `docs/debugging/MCP_INSPECTOR_GUIDE.md` | ~200 | Inspector guide |
| `scripts/start-inspector.sh` | ~20 | Startup script |

**Total**: ~770 lines documentation

---

## Verification Strategy

### Phase 2.6 Verification
```bash
# Run health tests
pytest python/tests/test_api_health.py -v

# Verify graceful degradation
# Stop Redis, rerun tests - degradation tests should pass
# Stop FAISS, rerun tests - degradation tests should pass
```

### Phase 2.7 Verification
```bash
# CLI Debug Client
python -m memory_mcp.cli_debug
> stats
> health
> store "Test" note test.py
> search "Test"

# Request Tracer
# Check ~/.claude-code-pp/logs/requests.jsonl

# Diagnostics
python -m memory_mcp.diagnostics
```

### Phase 2.8 Verification
```bash
# Install Bruno CLI
npm install -g @usebruno/cli

# Run collection
bruno run bruno/memory-mcp --env local
```

### Phase 2.9 Verification
```bash
# Launch MCP Inspector
./scripts/start-inspector.sh
# Open http://localhost:6274
# Test each tool manually
```

---

## Success Criteria

| Phase | Criteria |
|-------|----------|
| 2.6 | 25 health tests passing, all 10 endpoints verified |
| 2.7 | CLI functional, enhanced stats returning metrics, tracing working |
| 2.8 | Bruno collection runs successfully via CLI |
| 2.9 | MCP Inspector integration documented with startup script |
| **Overall** | 473 total tests (402 + 71), ~85% coverage |

---

## Timeline Summary

| Phase | Description | Effort | Lines | Tests |
|-------|-------------|--------|-------|-------|
| 2.6 | API Health Verification | 4-5 hours | ~450 | 25 |
| 2.7.1 | CLI Debug Client | 2-3 hours | ~500 | 10 |
| 2.7.2 | Enhanced Stats | 1-2 hours | ~200 | 8 |
| 2.7.3 | Request Tracing | 2-3 hours | ~450 | 10 |
| 2.7.4 | Diagnostics | 1 hour | ~350 | 8 |
| 2.8 | Bruno Collection | 2-3 hours | ~550 | - |
| 2.9 | MCP Inspector Docs | 1 hour | ~220 | - |
| **TOTAL** | **Immediate + Short-term** | **13-17 hours** | **~2,720** | **71** |

---

## Next Steps After Approval

1. **Phase 2.6**: Create `test_api_health.py` with 25 comprehensive health tests
2. **Phase 2.7.1**: Implement CLI debug client with interactive REPL
3. **Phase 2.7.2**: Enhance memory_stats tool handler in server.py
4. **Phase 2.7.3**: Implement request tracing system
5. **Phase 2.7.4**: Create component diagnostics module
6. **Phase 2.8**: Create Bruno collection with 15 .bru files
7. **Phase 2.9**: Write MCP Inspector integration documentation
8. **Verification**: Run all tests, verify 71 new tests pass
9. **Commit**: Comprehensive commit with all Phase 2.6-2.9 changes

---

*Plan synthesized from 3 parallel Explore agents + 1 Plan agent | 2026-01-21*
