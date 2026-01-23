# Development

Contributing and development setup for Claude Code++.

## Prerequisites

- Python 3.10+
- Swift 5.9+ (for System Controller)
- Docker (for infrastructure services)
- Git

## Repository Structure

```
claude-code-pp/
├── python/                    # Memory MCP server
│   ├── memory_mcp/           # Main package
│   │   ├── server.py         # MCP server implementation
│   │   ├── storage/          # Storage backends
│   │   ├── search/           # Search implementations
│   │   └── models/           # Data models
│   ├── tests/                # Test suite
│   └── pyproject.toml        # Python dependencies
├── swift-system-controller/   # macOS system control
│   ├── Sources/              # Swift source code
│   ├── Tests/                # Swift tests
│   └── Package.swift         # Swift package manifest
├── docker/                    # Docker configurations
│   ├── docker-compose.yaml   # Service definitions
│   └── Dockerfile.*          # Container builds
├── config/                    # Configuration templates
├── wiki/                      # Documentation source
└── .claude/                   # Claude Code extensions
    ├── agents/               # Custom agents
    ├── commands/             # Slash commands
    ├── rules/                # Context rules
    └── skills/               # Complex workflows
```

## Setting Up Development Environment

### 1. Clone Repository

```bash
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus
```

### 2. Python Setup

```bash
cd python
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### 3. Swift Setup (macOS only)

```bash
cd swift-system-controller
swift build
swift test
```

### 4. Start Infrastructure

```bash
docker-compose -f docker/docker-compose.yaml up -d
```

## Running Tests

### Python Tests

```bash
cd python
pytest                      # Run all tests
pytest --cov=memory_mcp     # With coverage
pytest -v -k "test_search"  # Specific tests
```

### Swift Tests

```bash
cd swift-system-controller
swift test
```

### Integration Tests

```bash
# Start services first
docker-compose -f docker/docker-compose.yaml up -d

# Run integration tests
cd python
pytest tests/integration/ -v
```

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Format with Black
- Lint with Ruff

```bash
# Format
black memory_mcp/

# Lint
ruff check memory_mcp/

# Type check
mypy memory_mcp/
```

### Swift

- Follow Swift API Design Guidelines
- Use SwiftFormat

```bash
swiftformat Sources/
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write tests first (TDD)
- Keep commits focused
- Follow existing patterns

### 3. Test Thoroughly

```bash
# Python
pytest --cov=memory_mcp --cov-report=html

# Swift
swift test
```

### 4. Submit PR

```bash
git push -u origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Adding New MCP Tools

### 1. Define the Tool

In `python/memory_mcp/server.py`:

```python
@server.tool()
async def my_new_tool(param1: str, param2: int = 10) -> dict:
    """
    Description of what this tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Result dictionary
    """
    # Implementation
    return {"success": True, "data": result}
```

### 2. Add Tests

In `python/tests/test_tools.py`:

```python
async def test_my_new_tool():
    result = await my_new_tool("test", param2=5)
    assert result["success"]
    assert "data" in result
```

### 3. Document

- Add to [[Memory-MCP-Tools]]
- Add schema to [[API-Reference]]

## Adding Storage Backends

### 1. Create Backend Class

In `python/memory_mcp/storage/`:

```python
from .base import StorageBackend

class MyBackend(StorageBackend):
    async def store(self, doc: Document) -> str:
        ...

    async def retrieve(self, doc_id: str) -> Document:
        ...

    async def search(self, query: str) -> list[Document]:
        ...
```

### 2. Register in Config

In `python/memory_mcp/config.py`:

```python
STORAGE_BACKENDS = {
    "sqlite": SQLiteBackend,
    "redis": RedisBackend,
    "mybackend": MyBackend,  # Add here
}
```

## Debugging

### Enable Debug Logging

```bash
export MEMORY_MCP_LOG_LEVEL=DEBUG
export MEMORY_MCP_LOG_FILE=~/.claude-code-pp/logs/debug.log
```

### MCP Debug Mode

```bash
claude --mcp-debug
```

### Test MCP Server Directly

```bash
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  python -m memory_mcp.server
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release commit
4. Tag release
5. Push to GitHub

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Getting Help

- [GitHub Issues](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/issues)
- [Discussions](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/discussions)

## Related Pages

- [[Architecture]] - System design
- [[Configuration]] - Setup options
- [[API-Reference]] - Tool schemas
- [[Troubleshooting]] - Common issues
