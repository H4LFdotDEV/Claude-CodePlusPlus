# Contributing to Claude Code++

Thank you for your interest in contributing to Claude Code++! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive. We're all here to build something great.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (for full/enterprise profiles)
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git
cd Claude-CodePlusPlus

# Install Python package in development mode
cd python
pip install -e ".[dev]"

# Run tests
pytest --cov=memory_mcp

# Run linting
ruff check memory_mcp
black --check memory_mcp
```

## Project Structure

```
claude-code-pp/
├── python/                    # Memory MCP Server
│   ├── memory_mcp/           # Main package
│   │   ├── server.py         # MCP server entry point
│   │   ├── handlers/         # Tool handlers
│   │   ├── storage/          # Storage backends
│   │   └── validation.py     # Input validation
│   └── tests/                # Python tests
├── swift-system-controller/   # macOS system control
├── openclaw/                  # OpenClaw integrations
│   └── extensions/           # OpenClaw plugins
├── CAIIDE++/                  # VS Code fork
│   └── extensions/           # Built-in extensions
├── docker/                    # Docker configurations
├── scripts/                   # Installation scripts
└── .claude/                   # Claude Code extensions
    ├── agents/               # Custom agents
    ├── commands/             # Slash commands
    ├── rules/                # Context rules
    └── skills/               # Complex workflows
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Changes

Follow the coding standards below. Write tests for new functionality.

### 3. Test Your Changes

```bash
# Python tests
cd python && pytest --cov=memory_mcp

# Install script tests
./scripts/test-install.sh

# TypeScript (if applicable)
cd openclaw && pnpm test
```

### 4. Commit Your Changes

We use conventional commits:

```bash
git commit -m "feat: add new memory tier"
git commit -m "fix: correct Redis connection handling"
git commit -m "docs: update installation guide"
git commit -m "refactor: simplify storage interface"
git commit -m "test: add integration tests for Graphiti"
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`

### 5. Push and Create PR

```bash
git push -u origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Coding Standards

### Python

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type Hints**: Required for public APIs
- **Docstrings**: Google style for public functions

```python
def store_memory(
    content: str,
    memory_type: str,
    importance: float = 0.5,
    tags: list[str] | None = None,
) -> MemoryEntry:
    """Store a memory in the appropriate tier.

    Args:
        content: The content to store.
        memory_type: Type of memory (preference, decision, etc.).
        importance: Importance score from 0.0 to 1.0.
        tags: Optional list of tags for categorization.

    Returns:
        The created MemoryEntry with assigned ID.

    Raises:
        ValidationError: If content is empty or importance out of range.
    """
```

### TypeScript

- **Formatter**: Prettier
- **Linter**: ESLint
- **Style**: Prefer functional patterns, immutable data

```typescript
interface MemoryEntry {
  readonly id: string;
  readonly content: string;
  readonly type: MemoryType;
  readonly createdAt: Date;
}

async function storeMemory(
  content: string,
  options: StoreOptions
): Promise<MemoryEntry> {
  // Implementation
}
```

### Shell Scripts

- Use `shellcheck` for linting
- Include `set -euo pipefail` at the top
- Quote all variables: `"$VAR"` not `$VAR`
- Use functions for organization

## Testing Guidelines

### Unit Tests

- Test individual functions in isolation
- Mock external dependencies
- Cover edge cases

### Integration Tests

- Test interactions between components
- Use real services when possible (via Docker)
- Mark with `@pytest.mark.integration`

### Test Coverage

- Aim for 80%+ coverage on new code
- Don't sacrifice test quality for coverage numbers

## Memory MCP Development

### Adding a New Tool

1. Define the schema in `tool_schemas.py`:

```python
NEW_TOOL_SCHEMA = {
    "name": "new_tool",
    "description": "What this tool does",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param"]
    }
}
```

2. Add handler in `handlers/`:

```python
async def handle_new_tool(params: dict) -> dict:
    validated = validate_new_tool_params(params)
    # Implementation
    return {"result": "..."}
```

3. Register in `server.py`
4. Add tests in `tests/`

### Adding a Storage Backend

1. Create new file in `storage/`
2. Implement the `StorageBackend` interface
3. Add configuration in `config.py`
4. Register in tier manager

## Pull Request Guidelines

### Before Submitting

- [ ] Tests pass locally
- [ ] Code is formatted and linted
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions
- [ ] No hardcoded secrets or paths

### PR Description Template

```markdown
## Summary
Brief description of changes.

## Changes
- Change 1
- Change 2

## Testing
How was this tested?

## Related Issues
Fixes #123
```

### Review Process

1. CI must pass
2. At least one approving review
3. No unresolved conversations
4. Squash and merge preferred

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, etc.)
- Error messages/logs

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternatives considered

## Getting Help

- Check the [Wiki](https://github.com/H4LFdotDEV/Claude-CodePlusPlus/wiki)
- Search existing issues
- Ask in discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
