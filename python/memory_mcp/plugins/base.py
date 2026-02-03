"""Base classes for Memory MCP plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.server import MemoryMCPServer


@dataclass
class ToolDefinition:
    """MCP tool definition for plugins."""

    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], dict]

    def to_mcp_schema(self) -> dict:
        """Convert to MCP tool schema format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MemoryPlugin(ABC):
    """Base class for Memory MCP plugins.

    Plugins can:
    - Provide custom MCP tools
    - Hook into memory operations (store, search, recall)
    - React to server lifecycle events
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        pass

    @property
    def version(self) -> str:
        """Plugin version string."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return ""

    @property
    def tools(self) -> List[ToolDefinition]:
        """MCP tools provided by this plugin."""
        return []

    # Lifecycle hooks
    def on_startup(self, server: "MemoryMCPServer") -> None:
        """Called when the server starts. Receives server reference."""
        pass

    def on_shutdown(self) -> None:
        """Called when the server stops."""
        pass

    # Memory operation hooks (return modified data or original)
    def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Hook called before storing a document. Return modified document."""
        return document

    def on_post_store(self, document: Dict[str, Any], doc_id: str) -> None:
        """Hook called after storing a document."""
        pass

    def on_search(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Hook called after search. Return modified results."""
        return results

    def on_recall(
        self,
        doc_id: str,
        document: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Hook called after recall. Return modified document."""
        return document

    def on_delete(self, doc_id: str) -> bool:
        """Hook called before delete. Return False to cancel deletion."""
        return True
