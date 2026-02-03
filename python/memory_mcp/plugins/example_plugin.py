"""Example plugin demonstrating Memory MCP Plugin SDK capabilities.

This is a complete example showing:
- Custom MCP tools
- Memory operation hooks
- Lifecycle management
"""

from typing import Any, Dict, List, Optional

from memory_mcp.plugins import MemoryPlugin, ToolDefinition


class ExamplePlugin(MemoryPlugin):
    """Example plugin with custom tools and hooks."""

    def __init__(self):
        self._storage: Dict[str, Any] = {}
        self._store_count = 0

    @property
    def name(self) -> str:
        """Unique plugin identifier."""
        return "example"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return "Example plugin demonstrating SDK capabilities"

    @property
    def tools(self) -> List[ToolDefinition]:
        """Custom MCP tools provided by this plugin."""
        return [
            ToolDefinition(
                name="get_plugin_storage",
                description="Get data from plugin's internal storage",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Storage key to retrieve"
                        }
                    },
                    "required": ["key"]
                },
                handler=self._handle_get_storage
            ),
            ToolDefinition(
                name="set_plugin_storage",
                description="Set data in plugin's internal storage",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Storage key"
                        },
                        "value": {
                            "description": "Value to store"
                        }
                    },
                    "required": ["key", "value"]
                },
                handler=self._handle_set_storage
            ),
            ToolDefinition(
                name="get_store_count",
                description="Get number of documents stored since plugin loaded",
                input_schema={
                    "type": "object",
                    "properties": {}
                },
                handler=self._handle_get_count
            )
        ]

    def _handle_get_storage(self, args: dict) -> dict:
        """Handle get_plugin_storage tool call."""
        key = args["key"]
        value = self._storage.get(key)
        return {
            "key": key,
            "value": value,
            "exists": key in self._storage
        }

    def _handle_set_storage(self, args: dict) -> dict:
        """Handle set_plugin_storage tool call."""
        key = args["key"]
        value = args["value"]
        self._storage[key] = value
        return {
            "key": key,
            "value": value,
            "success": True
        }

    def _handle_get_count(self, args: dict) -> dict:
        """Handle get_store_count tool call."""
        return {
            "count": self._store_count
        }

    # Lifecycle hooks
    def on_startup(self, server) -> None:
        """Called when server starts."""
        print(f"[{self.name}] Plugin started")

    def on_shutdown(self) -> None:
        """Called when server stops."""
        print(f"[{self.name}] Plugin shutting down. Total stores: {self._store_count}")

    # Memory operation hooks
    def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Called before storing a document.

        This example adds a plugin-specific tag to all stored documents.
        """
        # Add plugin tag
        tags = document.get("tags", [])
        if "example_plugin" not in tags:
            tags.append("example_plugin")

        return {
            **document,
            "tags": tags,
            "metadata": {
                **document.get("metadata", {}),
                "processed_by_example_plugin": True
            }
        }

    def on_post_store(self, document: Dict[str, Any], doc_id: str) -> None:
        """Called after document is stored."""
        self._store_count += 1

    def on_search(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Called after search.

        This example filters results to only include documents
        processed by this plugin.
        """
        # Only return documents tagged by this plugin
        return [
            r for r in results
            if "example_plugin" in r.get("tags", [])
        ]

    def on_recall(
        self,
        doc_id: str,
        document: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Called after recalling a document.

        This example adds recall metadata.
        """
        if document:
            return {
                **document,
                "metadata": {
                    **document.get("metadata", {}),
                    "recalled_by_example_plugin": True
                }
            }
        return document

    def on_delete(self, doc_id: str) -> bool:
        """Called before deleting a document.

        Return False to prevent deletion.
        This example blocks deletion of protected documents.
        """
        # Don't allow deletion of documents with "protected" tag
        # (In real implementation, would need to check document tags)
        return not doc_id.startswith("protected_")


# Plugin instance - this is required for the loader to find it
plugin = ExamplePlugin()
