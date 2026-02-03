# Memory MCP Plugin SDK

The Plugin SDK allows extending Memory MCP with custom tools and hooks without modifying core code.

## Features

- **Custom MCP Tools**: Add new tools that appear in Claude's tool list
- **Memory Hooks**: Intercept and modify memory operations (store, search, recall, delete)
- **Lifecycle Management**: React to server startup/shutdown events
- **Automatic Loading**: Plugins are automatically discovered from `~/.claude-code-pp/plugins/`

## Quick Start

### 1. Create a Plugin

Create `~/.claude-code-pp/plugins/my_plugin.py`:

```python
from typing import Any, Dict, List
from memory_mcp.plugins import MemoryPlugin, ToolDefinition

class MyPlugin(MemoryPlugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="hello",
                description="Say hello",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    },
                    "required": ["name"]
                },
                handler=self._handle_hello
            )
        ]

    def _handle_hello(self, args: dict) -> dict:
        return {"message": f"Hello, {args['name']}!"}

    def on_startup(self, server) -> None:
        print(f"[{self.name}] Plugin loaded!")

# Required: expose plugin instance
plugin = MyPlugin()
```

### 2. Use the Plugin

The plugin is automatically loaded when Memory MCP starts. The tool appears as `my_plugin:hello` in Claude's tool list.

## Plugin API

### Base Class: MemoryPlugin

All plugins must inherit from `MemoryPlugin`:

```python
from memory_mcp.plugins import MemoryPlugin

class MyPlugin(MemoryPlugin):
    @property
    def name(self) -> str:
        """Unique plugin identifier (required)."""
        return "my_plugin"
```

#### Required Properties

- `name: str` - Unique plugin identifier (used for tool namespacing)

#### Optional Properties

- `version: str` - Plugin version (default: "1.0.0")
- `description: str` - Plugin description (default: "")
- `tools: List[ToolDefinition]` - MCP tools provided by plugin (default: [])

#### Lifecycle Hooks

```python
def on_startup(self, server: MemoryMCPServer) -> None:
    """Called when server starts. Receives server reference."""
    pass

def on_shutdown(self) -> None:
    """Called when server stops."""
    pass
```

#### Memory Operation Hooks

All hooks are optional. Return modified data or original to pass through.

```python
def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
    """Called before storing. Return modified document."""
    return document

def on_post_store(self, document: Dict[str, Any], doc_id: str) -> None:
    """Called after storing."""
    pass

def on_search(
    self,
    query: str,
    results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Called after search. Return modified results."""
    return results

def on_recall(
    self,
    doc_id: str,
    document: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Called after recall. Return modified document."""
    return document

def on_delete(self, doc_id: str) -> bool:
    """Called before delete. Return False to prevent deletion."""
    return True
```

### Tool Definition

Define custom MCP tools:

```python
from memory_mcp.plugins import ToolDefinition

tool = ToolDefinition(
    name="my_tool",
    description="Tool description",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    },
    handler=lambda args: {"result": args["param"]}
)
```

#### Properties

- `name: str` - Tool name (will be namespaced as `{plugin_name}:{tool_name}`)
- `description: str` - Tool description shown in Claude
- `input_schema: dict` - JSON Schema for tool parameters
- `handler: Callable[[dict], dict]` - Function to handle tool calls

#### Handler Function

Handler receives arguments dict and returns result dict:

```python
def handler(args: dict) -> dict:
    param = args.get("param")
    # Process...
    return {"result": "success", "data": param}
```

## Use Cases

### 1. Custom Tools for Domain-Specific Operations

```python
class DatabasePlugin(MemoryPlugin):
    @property
    def name(self) -> str:
        return "database"

    @property
    def tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="query_stats",
                description="Get database statistics",
                input_schema={"type": "object", "properties": {}},
                handler=self._get_stats
            )
        ]

    def _get_stats(self, args: dict) -> dict:
        # Query database
        return {"tables": 42, "rows": 10000}

plugin = DatabasePlugin()
```

### 2. Automatic Tagging and Enrichment

```python
class TaggerPlugin(MemoryPlugin):
    @property
    def name(self) -> str:
        return "tagger"

    def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
        # Automatically add tags based on content
        content = document.get("content", "")
        tags = document.get("tags", [])

        if "TODO" in content:
            tags.append("todo")
        if "FIXME" in content:
            tags.append("fixme")

        return {**document, "tags": tags}

plugin = TaggerPlugin()
```

### 3. Access Control and Filtering

```python
class SecurityPlugin(MemoryPlugin):
    @property
    def name(self) -> str:
        return "security"

    def on_search(self, query: str, results: List[Dict]) -> List[Dict]:
        # Filter out sensitive documents
        return [
            r for r in results
            if "sensitive" not in r.get("tags", [])
        ]

    def on_delete(self, doc_id: str) -> bool:
        # Prevent deletion of protected documents
        return not doc_id.startswith("protected_")

plugin = SecurityPlugin()
```

### 4. Analytics and Logging

```python
class AnalyticsPlugin(MemoryPlugin):
    def __init__(self):
        self.stats = {"stores": 0, "searches": 0, "recalls": 0}

    @property
    def name(self) -> str:
        return "analytics"

    @property
    def tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_stats",
                description="Get usage statistics",
                input_schema={"type": "object", "properties": {}},
                handler=lambda _: self.stats
            )
        ]

    def on_post_store(self, document: Dict, doc_id: str) -> None:
        self.stats["stores"] += 1

    def on_search(self, query: str, results: List[Dict]) -> List[Dict]:
        self.stats["searches"] += 1
        return results

    def on_recall(self, doc_id: str, doc: Optional[Dict]) -> Optional[Dict]:
        self.stats["recalls"] += 1
        return doc

plugin = AnalyticsPlugin()
```

## Plugin Loading

### Automatic Loading

Plugins are automatically loaded from `~/.claude-code-pp/plugins/` on server startup.

### Manual Loading

```python
from memory_mcp.plugins import load_plugins
from pathlib import Path

registry = load_plugins(Path("/path/to/plugins"))
```

### Registry Operations

```python
from memory_mcp.plugins import PluginRegistry

registry = PluginRegistry()

# Register plugin
registry.register(my_plugin)

# Get plugin
plugin = registry.get_plugin("my_plugin")

# Get all plugins
plugins = registry.get_all_plugins()

# Unregister plugin
registry.unregister("my_plugin")

# Get statistics
stats = registry.get_stats()
```

## Best Practices

### 1. Error Handling

Always handle errors gracefully:

```python
def _handle_tool(self, args: dict) -> dict:
    try:
        result = risky_operation(args)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 2. Immutability

Return new objects, don't mutate inputs:

```python
def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
    # GOOD: Create new dict
    return {**document, "enriched": True}

    # BAD: Mutate input
    # document["enriched"] = True
    # return document
```

### 3. Performance

Keep hooks fast - they're called for every operation:

```python
def on_search(self, query: str, results: List[Dict]) -> List[Dict]:
    # GOOD: Simple filter
    return [r for r in results if r.get("visible", True)]

    # BAD: Expensive operation
    # for r in results:
    #     expensive_api_call(r)
    # return results
```

### 4. Namespacing

Use unique plugin names to avoid conflicts:

```python
@property
def name(self) -> str:
    return "mycompany_myplugin"  # Unique identifier
```

### 5. Documentation

Document your plugin's purpose and tools:

```python
class MyPlugin(MemoryPlugin):
    """
    Plugin for XYZ functionality.

    Provides:
    - tool1: Does X
    - tool2: Does Y

    Hooks:
    - on_store: Adds Z metadata
    """
    pass
```

## Testing

Test your plugin before deployment:

```python
import pytest
from my_plugin import MyPlugin

def test_plugin_tool():
    plugin = MyPlugin()
    tool = plugin.tools[0]
    result = tool.handler({"param": "value"})
    assert result["success"] is True

def test_plugin_hook():
    plugin = MyPlugin()
    doc = {"content": "test"}
    modified = plugin.on_store(doc)
    assert "enriched" in modified
```

## Example Plugins

See `example_plugin.py` for a complete working example demonstrating:
- Custom tools with state management
- All hook types
- Lifecycle management
- Best practices

## Troubleshooting

### Plugin Not Loading

1. Check file is in `~/.claude-code-pp/plugins/`
2. Verify file ends with `.py` and doesn't start with `_`
3. Ensure `plugin = MyPlugin()` at module level
4. Check logs for import errors

### Tool Not Appearing

1. Verify tool is in `tools` property list
2. Check tool name doesn't conflict with core tools
3. Restart Memory MCP server

### Hook Not Called

1. Ensure hook method name is correct (e.g., `on_store` not `onStore`)
2. Check hook is returning data (return original if no changes)
3. Verify plugin is registered in registry

## Security Considerations

- **Validate inputs**: Don't trust tool arguments
- **Limit access**: Use hooks to enforce access control
- **Isolate state**: Don't share state between plugins
- **Handle errors**: Don't let exceptions crash the server

## Future Enhancements

Planned features:
- Plugin dependencies and ordering
- Inter-plugin communication
- Plugin configuration files
- Hot reload without restart
- Plugin marketplace/registry
