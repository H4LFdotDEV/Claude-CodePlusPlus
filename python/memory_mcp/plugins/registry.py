"""Plugin registry for managing loaded plugins."""

import logging
from typing import Any, Callable, Dict, List, Optional

from .base import MemoryPlugin, ToolDefinition

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for loaded plugins and their tools."""

    def __init__(self):
        self._plugins: Dict[str, MemoryPlugin] = {}
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, plugin: MemoryPlugin) -> None:
        """Register a plugin."""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' already registered")

        self._plugins[plugin.name] = plugin

        # Register plugin tools with namespaced names
        for tool in plugin.tools:
            tool_name = f"{plugin.name}:{tool.name}"
            self._tools[tool_name] = tool
            logger.info(f"Registered tool: {tool_name}")

        logger.info(
            f"Registered plugin: {plugin.name} v{plugin.version} "
            f"({len(plugin.tools)} tools)"
        )

    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin by name."""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]

        # Remove plugin tools
        for tool in plugin.tools:
            tool_name = f"{plugin_name}:{tool.name}"
            self._tools.pop(tool_name, None)

        # Call shutdown hook
        try:
            plugin.on_shutdown()
        except Exception as e:
            logger.warning(f"Plugin {plugin_name} shutdown error: {e}")

        del self._plugins[plugin_name]
        return True

    def get_plugin(self, name: str) -> Optional[MemoryPlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_all_plugins(self) -> List[MemoryPlugin]:
        """Get all registered plugins."""
        return list(self._plugins.values())

    def get_all_tool_schemas(self) -> List[dict]:
        """Get MCP schemas for all plugin tools."""
        return [tool.to_mcp_schema() for tool in self._tools.values()]

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get a tool by its namespaced name."""
        return self._tools.get(tool_name)

    def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Route tool call to plugin handler."""
        if tool_name not in self._tools:
            raise ValueError(f"Unknown plugin tool: {tool_name}")

        return self._tools[tool_name].handler(arguments)

    def call_hook(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Call a hook on all plugins, returning the last non-None result."""
        result = args[0] if args else None

        for plugin in self._plugins.values():
            hook = getattr(plugin, hook_name, None)
            if hook and callable(hook):
                try:
                    hook_result = hook(*args, **kwargs)
                    if hook_result is not None:
                        result = hook_result
                        # Update args for chained hooks
                        if args:
                            args = (result,) + args[1:]
                except Exception as e:
                    logger.warning(
                        f"Plugin {plugin.name} hook {hook_name} error: {e}"
                    )

        return result

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "plugin_count": len(self._plugins),
            "tool_count": len(self._tools),
            "plugins": [
                {
                    "name": p.name,
                    "version": p.version,
                    "tools": len(p.tools),
                }
                for p in self._plugins.values()
            ],
        }
