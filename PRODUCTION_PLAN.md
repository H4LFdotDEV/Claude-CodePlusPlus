# Claude Code++ Production Readiness Plan

## Status: READY FOR REVIEW

## Overview
Comprehensive plan to make Claude Code++ production-ready, addressing security vulnerabilities, code quality, CI/CD, and performance optimizations.

---

## Phase 1: Security Fixes (CRITICAL)

### 1.1 Path Traversal Protection
**Files:** `python/memory_mcp/vault_manager.py`
**Lines:** 81-83 (`_full_path` method)
**Issue:** No validation of relative paths - attacker can use `../../etc/passwd` to escape vault
**Current Code:**
```python
def _full_path(self, relative_path: str) -> str:
    """Get full filesystem path."""
    return os.path.join(self.path, relative_path)  # NO VALIDATION!
```
**Solution:**
```python
def _full_path(self, relative_path: str) -> str:
    """Get full filesystem path with path traversal protection."""
    # Normalize and resolve the path
    full = os.path.normpath(os.path.join(self.path, relative_path))
    # Ensure result is still within vault
    if not full.startswith(os.path.normpath(self.path) + os.sep):
        raise ValueError(f"Path traversal detected: {relative_path}")
    return full
```
**Affected Methods:** `read()`, `write()`, `delete()`, `exists()`, `list_notes()`

### 1.2 Input Validation Hardening
**Files:** `python/memory_mcp/server.py`
**Issue:** Tool inputs not fully validated before processing
**Solution:**
- Add Pydantic models for all tool inputs
- Validate `type` against allowed document types enum
- Sanitize `tags` array (alphanumeric + hyphen only)
- Validate `project` names (no special chars)
- Limit `content` size (max 1MB)
- Validate `limit` ranges (1-1000)

### 1.3 FTS Query Injection
**Files:** `python/memory_mcp/sqlite_index.py`
**Line:** 252
**Issue:** User queries passed directly to FTS5 MATCH
**Solution:** Escape FTS5 special characters (`"`, `*`, `OR`, `AND`, `NOT`, `NEAR`)

---

## Phase 2: Code Quality Fixes (HIGH)

### 2.1 Python Deprecation Warnings
**Issue:** `datetime.utcnow()` deprecated in Python 3.12+
**Files & Lines:**
- `python/memory_mcp/sqlite_index.py`: lines 40, 202
- `python/memory_mcp/redis_client.py`: lines 115, 147
- `python/memory_mcp/server.py`: lines 89, 156, 298
- `python/memory_mcp/embedding_provider.py`: line 45
- `python/tests/test_redis_client.py`: lines 115, 147
**Solution:**
```python
# OLD
from datetime import datetime
timestamp = datetime.utcnow()

# NEW
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

### 2.2 Thread-Safe Configuration
**Files:** `python/memory_mcp/config.py`
**Lines:** 130-151
**Issue:** Global singleton has race condition
**Current Code:**
```python
_config: Optional[MemoryConfig] = None

def get_config() -> MemoryConfig:
    global _config
    if _config is None:  # RACE CONDITION
        _config = MemoryConfig.from_yaml(config_path)
    return _config
```
**Solution:**
```python
import threading

_config: Optional[MemoryConfig] = None
_config_lock = threading.Lock()

def get_config() -> MemoryConfig:
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:  # Double-check locking
                _config = MemoryConfig.from_yaml(config_path)
    return _config
```

### 2.3 Swift Force Unwrap Safety
**Files:** `swift-system-controller/Sources/SystemController/SystemController.swift`
**Lines:** 520-521, 530-531
**Issue:** Force unwraps can crash on nil
**Current Code:**
```swift
let positionValue = AXValueCreate(.cgPoint, &position)!
let sizeValue = AXValueCreate(.cgSize, &newSize)!
```
**Solution:**
```swift
guard let positionValue = AXValueCreate(.cgPoint, &position) else {
    throw SystemControllerError.accessibilityError("Failed to create position value")
}
guard let sizeValue = AXValueCreate(.cgSize, &newSize) else {
    throw SystemControllerError.accessibilityError("Failed to create size value")
}
```

### 2.4 Swift Error Handling
**Files:** `swift-system-controller/Sources/SystemController/ActionLogger.swift`
**Lines:** 61, 86
**Issue:** `try?` silently swallows errors
**Solution:** Replace with proper error handling and logging

### 2.5 Swift Log Rotation
**Files:** `swift-system-controller/Sources/SystemController/ActionLogger.swift`
**Issue:** Logs grow unbounded
**Solution:**
```swift
private let maxLogSize: Int64 = 10 * 1024 * 1024  // 10 MB
private let maxLogFiles: Int = 5

func rotateIfNeeded() throws {
    let fileSize = try FileManager.default.attributesOfItem(atPath: logPath)[.size] as? Int64 ?? 0
    if fileSize > maxLogSize {
        try rotateLog()
    }
}

private func rotateLog() throws {
    // Rotate logs: action.log -> action.log.1 -> action.log.2 -> ...
    for i in (1..<maxLogFiles).reversed() {
        let oldPath = "\(logPath).\(i)"
        let newPath = "\(logPath).\(i + 1)"
        if FileManager.default.fileExists(atPath: oldPath) {
            try FileManager.default.moveItem(atPath: oldPath, toPath: newPath)
        }
    }
    try FileManager.default.moveItem(atPath: logPath, toPath: "\(logPath).1")
}
```

---

## Phase 3: CI/CD Pipeline (HIGH)

### 3.1 GitHub Actions Workflow
**File:** `.github/workflows/ci.yml` (new)
**Components:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd python
          pip install -e ".[dev]"
      - name: Lint with ruff
        run: |
          cd python
          ruff check .
          ruff format --check .
      - name: Type check
        run: |
          cd python
          mypy memory_mcp --ignore-missing-imports
      - name: Run tests
        run: |
          cd python
          pytest tests/ -v --cov=memory_mcp --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  swift-build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Swift
        run: |
          cd swift-system-controller
          swift build
      - name: Run Swift tests
        run: |
          cd swift-system-controller
          swift test
      - name: Lint with SwiftLint
        run: |
          brew install swiftlint
          cd swift-system-controller
          swiftlint --strict

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: |
          docker compose -f docker/docker-compose.yml build
```

### 3.2 Docker Health Checks
**File:** `docker/docker-compose.yml`
**Issue:** `depends_on` should use `condition: service_healthy`
**Solution:** Update all service dependencies

---

## Phase 4: Performance Optimizations (MEDIUM)

### 4.1 Async Tool Handlers
**Files:** `python/memory_mcp/server.py`
**Lines:** 371, 441, 453
**Issue:** Blocking operations freeze event loop
**Solution:**
```python
# Convert blocking embedding calls to async
async def handle_memory_store(self, args: dict) -> dict:
    content = args.get("content", "")

    # Run embedding in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None,
        self.embedding_provider.embed,
        content
    )

    # Rest of the method...
```

### 4.2 O(n²) Deduplication Fix
**Files:** `python/memory_mcp/server.py`
**Line:** 453
**Issue:** Linear scan for each result
**Current Code:**
```python
if not any(r["id"] == doc.id for r in results):  # O(n) per doc = O(n²)
```
**Solution:**
```python
seen_ids: set[str] = set()
for doc in documents:
    if doc.id not in seen_ids:
        seen_ids.add(doc.id)
        results.append(doc.to_dict())
```

### 4.3 FAISS Index Rebuild
**Files:** `python/memory_mcp/faiss_index.py`
**Issue:** Lazy deletion never triggers rebuild, index degrades
**Solution:**
```python
def needs_rebuild(self) -> bool:
    """Check if index needs compaction."""
    if self.total_added == 0:
        return False
    deletion_ratio = self.deleted_count / self.total_added
    return deletion_ratio > 0.3  # 30% threshold

def maybe_rebuild(self) -> None:
    """Rebuild index if needed."""
    if self.needs_rebuild():
        self.rebuild()
```

### 4.4 SQLite Optimizations
**Files:** `python/memory_mcp/sqlite_index.py`
**Issue:** Missing performance PRAGMAs
**Solution:** Add to `__init__`:
```python
self.conn.execute("PRAGMA journal_mode=WAL")
self.conn.execute("PRAGMA synchronous=NORMAL")
self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
self.conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
```

### 4.5 Embedding Cache Integration
**Files:** `python/memory_mcp/server.py`, `python/memory_mcp/redis_client.py`
**Issue:** `cache_embedding()` and `get_cached_embedding()` methods exist but NEVER called
**Solution:** Integrate into embedding workflow:
```python
def get_embedding(self, text: str) -> np.ndarray:
    # Check cache first
    if self.redis_client:
        cached = self.redis_client.get_cached_embedding(text)
        if cached is not None:
            return np.array(cached, dtype=np.float32)

    # Generate embedding
    embedding = self.embedding_provider.embed(text)

    # Cache for next time
    if self.redis_client:
        self.redis_client.cache_embedding(text, embedding.tolist(), ttl=86400)

    return embedding
```

### 4.6 Query Cache TTL
**Files:** `python/memory_mcp/redis_client.py`
**Lines:** 204-230
**Issue:** 5-minute TTL too short for semantic queries
**Solution:** Increase to 1 hour (3600 seconds)

---

## Phase 5: Testing Infrastructure (MEDIUM)

### 5.1 Enable Skipped Tests
**Current:** 90 passing, 54 skipped
**Goal:** Run all tests with optional dependencies
**Solution:**
- Install redis, httpx in CI environment
- Add conditional test markers for optional features
- Create test fixtures that mock unavailable services

### 5.2 Add Missing Tests
- Path traversal protection tests
- Thread safety stress tests
- Async handler tests
- Log rotation tests

---

## Implementation Order

1. **CRITICAL** (Do First):
   - [ ] 1.1 Path traversal protection
   - [ ] 1.2 Input validation
   - [ ] 1.3 FTS query injection

2. **HIGH** (Do Second):
   - [ ] 2.1 Deprecation warnings (11 instances)
   - [ ] 2.2 Thread-safe config
   - [ ] 2.3 Swift force unwraps
   - [ ] 2.4 Swift error handling
   - [ ] 2.5 Log rotation
   - [ ] 3.1 CI/CD workflow
   - [ ] 3.2 Docker health checks

3. **MEDIUM** (Do Third):
   - [ ] 4.1 Async handlers
   - [ ] 4.2 O(n²) deduplication
   - [ ] 4.3 FAISS rebuild
   - [ ] 4.4 SQLite PRAGMAs
   - [ ] 4.5 Embedding cache integration
   - [ ] 4.6 Query cache TTL
   - [ ] 5.1 Enable skipped tests
   - [ ] 5.2 Add security tests

---

## Verification Plan

After implementation, verify:

1. **Security**
   ```bash
   # Test path traversal protection
   python -c "from memory_mcp.vault_manager import VaultManager; v = VaultManager('/tmp/test'); v.read('../../etc/passwd')"
   # Should raise ValueError
   ```

2. **Tests Pass**
   ```bash
   cd python && pytest tests/ -v
   cd swift-system-controller && swift test
   ```

3. **CI/CD Works**
   - Push to branch
   - Verify all jobs pass in GitHub Actions

4. **Performance**
   - Benchmark embedding operations before/after caching
   - Monitor log file sizes over time

---

## Risk Assessment

| Fix | Risk | Mitigation |
|-----|------|------------|
| Path traversal | Low | Simple validation, well-tested pattern |
| Thread safety | Low | Double-checked locking is standard |
| Async handlers | Medium | May expose race conditions - test thoroughly |
| FAISS rebuild | Medium | Could be slow for large indexes - add progress logging |
| SQLite PRAGMAs | Low | Well-documented settings |

---

## Estimated Changes

- **Python files:** ~15 files modified
- **Swift files:** 2 files modified
- **New files:** 1 (.github/workflows/ci.yml)
- **Lines changed:** ~300-400

---

*Plan ready for review and approval.*
