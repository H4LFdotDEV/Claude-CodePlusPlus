"""Tests for the Plugin SDK."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from memory_mcp.plugins import (
    MemoryPlugin, PluginRegistry, ToolDefinition, load_plugins,
    approve_plugin, revoke_plugin, list_plugins, verify_plugin, PluginSecurityError
)
from memory_mcp.plugins.loader import load_plugin_from_file


class TestToolDefinition:
    """Test ToolDefinition functionality."""

    def test_create_tool_definition(self):
        """Test creating a tool definition."""
        def handler(args):
            return {"result": "success"}

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                },
                "required": ["param1"]
            },
            handler=handler
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.handler({"param1": "value"}) == {"result": "success"}

    def test_to_mcp_schema(self):
        """Test converting tool to MCP schema."""
        def handler(args):
            return {}

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                }
            },
            handler=handler
        )

        schema = tool.to_mcp_schema()

        assert schema == {
            "name": "test_tool",
            "description": "A test tool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                }
            }
        }


class TestMemoryPlugin:
    """Test MemoryPlugin base class."""

    def test_plugin_must_implement_name(self):
        """Test that plugin must implement name property."""
        with pytest.raises(TypeError):
            # Cannot instantiate abstract class
            MemoryPlugin()

    def test_plugin_defaults(self):
        """Test plugin default values."""
        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

        plugin = TestPlugin()

        assert plugin.name == "test"
        assert plugin.version == "1.0.0"
        assert plugin.description == ""
        assert plugin.tools == []

    def test_plugin_custom_values(self):
        """Test plugin with custom values."""
        def handler(args):
            return {"result": "ok"}

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "custom"

            @property
            def version(self) -> str:
                return "2.0.0"

            @property
            def description(self) -> str:
                return "Custom plugin"

            @property
            def tools(self) -> List[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="custom_tool",
                        description="Custom tool",
                        input_schema={"type": "object"},
                        handler=handler
                    )
                ]

        plugin = TestPlugin()

        assert plugin.name == "custom"
        assert plugin.version == "2.0.0"
        assert plugin.description == "Custom plugin"
        assert len(plugin.tools) == 1
        assert plugin.tools[0].name == "custom_tool"

    def test_lifecycle_hooks(self):
        """Test lifecycle hooks."""
        called = []

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            def on_startup(self, server) -> None:
                called.append("startup")

            def on_shutdown(self) -> None:
                called.append("shutdown")

        plugin = TestPlugin()
        plugin.on_startup(None)
        plugin.on_shutdown()

        assert called == ["startup", "shutdown"]

    def test_memory_hooks(self):
        """Test memory operation hooks."""
        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                return {**document, "modified": True}

            def on_post_store(self, document: Dict[str, Any], doc_id: str) -> None:
                pass

            def on_search(
                self,
                query: str,
                results: List[Dict[str, Any]]
            ) -> List[Dict[str, Any]]:
                return [{"modified": True} for r in results]

            def on_recall(
                self,
                doc_id: str,
                document: Optional[Dict[str, Any]]
            ) -> Optional[Dict[str, Any]]:
                if document:
                    return {**document, "recalled": True}
                return document

            def on_delete(self, doc_id: str) -> bool:
                return doc_id != "protected"

        plugin = TestPlugin()

        # Test on_store
        doc = {"content": "test"}
        modified = plugin.on_store(doc)
        assert modified["modified"] is True
        assert modified["content"] == "test"

        # Test on_post_store (no exception)
        plugin.on_post_store(doc, "id123")

        # Test on_search
        results = [{"id": "1"}, {"id": "2"}]
        modified_results = plugin.on_search("query", results)
        assert all(r.get("modified") for r in modified_results)

        # Test on_recall
        recalled = plugin.on_recall("id", {"content": "test"})
        assert recalled["recalled"] is True

        # Test on_delete
        assert plugin.on_delete("id") is True
        assert plugin.on_delete("protected") is False


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

        registry = PluginRegistry()
        plugin = TestPlugin()

        registry.register(plugin)

        assert registry.get_plugin("test") == plugin
        assert len(registry.get_all_plugins()) == 1

    def test_register_duplicate_plugin(self):
        """Test registering duplicate plugin raises error."""
        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

        registry = PluginRegistry()
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()

        registry.register(plugin1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(plugin2)

    def test_register_plugin_with_tools(self):
        """Test registering plugin with tools."""
        def handler(args):
            return {"result": args.get("input")}

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def tools(self) -> List[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="tool1",
                        description="Tool 1",
                        input_schema={"type": "object"},
                        handler=handler
                    ),
                    ToolDefinition(
                        name="tool2",
                        description="Tool 2",
                        input_schema={"type": "object"},
                        handler=handler
                    )
                ]

        registry = PluginRegistry()
        plugin = TestPlugin()

        registry.register(plugin)

        # Check namespaced tool names
        tool1 = registry.get_tool("test:tool1")
        tool2 = registry.get_tool("test:tool2")

        assert tool1 is not None
        assert tool2 is not None
        assert tool1.name == "tool1"
        assert tool2.name == "tool2"

        # Check tool schemas
        schemas = registry.get_all_tool_schemas()
        assert len(schemas) == 2

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        shutdown_called = []

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            def on_shutdown(self) -> None:
                shutdown_called.append(True)

        registry = PluginRegistry()
        plugin = TestPlugin()

        registry.register(plugin)
        assert registry.unregister("test") is True
        assert shutdown_called == [True]
        assert registry.get_plugin("test") is None

    def test_unregister_nonexistent_plugin(self):
        """Test unregistering nonexistent plugin returns False."""
        registry = PluginRegistry()
        assert registry.unregister("nonexistent") is False

    def test_handle_tool_call(self):
        """Test routing tool calls to plugin handlers."""
        def handler(args):
            return {"result": args.get("input", "") + "_processed"}

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def tools(self) -> List[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="process",
                        description="Process data",
                        input_schema={"type": "object"},
                        handler=handler
                    )
                ]

        registry = PluginRegistry()
        plugin = TestPlugin()
        registry.register(plugin)

        result = registry.handle_tool_call("test:process", {"input": "data"})
        assert result == {"result": "data_processed"}

    def test_handle_unknown_tool_call(self):
        """Test calling unknown tool raises error."""
        registry = PluginRegistry()

        with pytest.raises(ValueError, match="Unknown plugin tool"):
            registry.handle_tool_call("unknown:tool", {})

    def test_call_hook(self):
        """Test calling hooks on all plugins."""
        call_order = []

        class Plugin1(MemoryPlugin):
            @property
            def name(self) -> str:
                return "plugin1"

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                call_order.append("plugin1")
                return {**document, "plugin1": True}

        class Plugin2(MemoryPlugin):
            @property
            def name(self) -> str:
                return "plugin2"

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                call_order.append("plugin2")
                return {**document, "plugin2": True}

        registry = PluginRegistry()
        registry.register(Plugin1())
        registry.register(Plugin2())

        doc = {"content": "test"}
        result = registry.call_hook("on_store", doc)

        # Both hooks should be called
        assert "plugin1" in call_order
        assert "plugin2" in call_order

        # Result should have both modifications
        assert result["plugin1"] is True
        assert result["plugin2"] is True

    def test_call_hook_with_exception(self):
        """Test hook exceptions don't break chain."""
        call_order = []

        class Plugin1(MemoryPlugin):
            @property
            def name(self) -> str:
                return "plugin1"

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                call_order.append("plugin1")
                raise RuntimeError("Plugin1 error")

        class Plugin2(MemoryPlugin):
            @property
            def name(self) -> str:
                return "plugin2"

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                call_order.append("plugin2")
                return {**document, "plugin2": True}

        registry = PluginRegistry()
        registry.register(Plugin1())
        registry.register(Plugin2())

        doc = {"content": "test"}
        result = registry.call_hook("on_store", doc)

        # Both hooks should be attempted
        assert call_order == ["plugin1", "plugin2"]

        # Plugin2 result should still be returned
        assert result["plugin2"] is True

    def test_get_stats(self):
        """Test getting registry statistics."""
        def handler(args):
            return {}

        class TestPlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "2.0.0"

            @property
            def tools(self) -> List[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="tool1",
                        description="Tool 1",
                        input_schema={"type": "object"},
                        handler=handler
                    )
                ]

        registry = PluginRegistry()
        registry.register(TestPlugin())

        stats = registry.get_stats()

        assert stats["plugin_count"] == 1
        assert stats["tool_count"] == 1
        assert len(stats["plugins"]) == 1
        assert stats["plugins"][0]["name"] == "test"
        assert stats["plugins"][0]["version"] == "2.0.0"
        assert stats["plugins"][0]["tools"] == 1


class TestPluginLoader:
    """Test plugin loader functionality."""

    def test_load_plugin_from_file(self):
        """Test loading a plugin from a Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text("""
from memory_mcp.plugins import MemoryPlugin

class TestPlugin(MemoryPlugin):
    @property
    def name(self):
        return "test_plugin"

    @property
    def version(self):
        return "1.0.0"

plugin = TestPlugin()
""")

            loaded_plugin = load_plugin_from_file(plugin_file)

            assert loaded_plugin is not None
            assert loaded_plugin.name == "test_plugin"
            assert loaded_plugin.version == "1.0.0"

    def test_load_plugin_from_file_no_plugin_var(self):
        """Test loading file without plugin variable returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text("""
# No plugin variable defined
x = 42
""")

            loaded_plugin = load_plugin_from_file(plugin_file)
            assert loaded_plugin is None

    def test_load_plugin_from_file_invalid_plugin(self):
        """Test loading file with invalid plugin type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text("""
# plugin is not a MemoryPlugin instance
plugin = "not a plugin"
""")

            loaded_plugin = load_plugin_from_file(plugin_file)
            assert loaded_plugin is None

    def test_load_plugin_from_file_syntax_error(self):
        """Test loading file with syntax error returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text("""
# Invalid Python syntax
def broken(
""")

            loaded_plugin = load_plugin_from_file(plugin_file)
            assert loaded_plugin is None

    def test_load_plugins_from_directory(self):
        """Test loading multiple plugins from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            # Create plugin 1
            (plugin_dir / "plugin1.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class Plugin1(MemoryPlugin):
    @property
    def name(self):
        return "plugin1"

plugin = Plugin1()
""")

            # Create plugin 2
            (plugin_dir / "plugin2.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class Plugin2(MemoryPlugin):
    @property
    def name(self):
        return "plugin2"

plugin = Plugin2()
""")

            # Create file to ignore (starts with _)
            (plugin_dir / "_ignore.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class IgnorePlugin(MemoryPlugin):
    @property
    def name(self):
        return "ignore"

plugin = IgnorePlugin()
""")

            # Use unsafe_mode for testing (plugins not in allowlist)
            registry = load_plugins(plugin_dir, unsafe_mode=True)

            assert registry.get_plugin("plugin1") is not None
            assert registry.get_plugin("plugin2") is not None
            assert registry.get_plugin("ignore") is None

    def test_load_plugins_nonexistent_directory(self):
        """Test loading from nonexistent directory returns empty registry."""
        registry = load_plugins(Path("/nonexistent/path"))
        assert len(registry.get_all_plugins()) == 0

    def test_load_plugins_with_existing_registry(self):
        """Test loading plugins into existing registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            (plugin_dir / "plugin.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class TestPlugin(MemoryPlugin):
    @property
    def name(self):
        return "test"

plugin = TestPlugin()
""")

            # Create registry with existing plugin
            class ExistingPlugin(MemoryPlugin):
                @property
                def name(self) -> str:
                    return "existing"

            registry = PluginRegistry()
            registry.register(ExistingPlugin())

            # Load new plugins into existing registry (use unsafe_mode for testing)
            registry = load_plugins(plugin_dir, registry, unsafe_mode=True)

            assert len(registry.get_all_plugins()) == 2
            assert registry.get_plugin("existing") is not None
            assert registry.get_plugin("test") is not None


class TestEndToEndPlugin:
    """End-to-end test with a complete sample plugin."""

    def test_complete_plugin_workflow(self):
        """Test a complete plugin with tools and hooks."""
        results = []

        def echo_handler(args):
            return {"echo": args.get("message", "")}

        def uppercase_handler(args):
            return {"result": args.get("text", "").upper()}

        class SamplePlugin(MemoryPlugin):
            @property
            def name(self) -> str:
                return "sample"

            @property
            def version(self) -> str:
                return "1.2.3"

            @property
            def description(self) -> str:
                return "A sample plugin for testing"

            @property
            def tools(self) -> List[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="echo",
                        description="Echo a message",
                        input_schema={
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"}
                            },
                            "required": ["message"]
                        },
                        handler=echo_handler
                    ),
                    ToolDefinition(
                        name="uppercase",
                        description="Convert text to uppercase",
                        input_schema={
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"}
                            },
                            "required": ["text"]
                        },
                        handler=uppercase_handler
                    )
                ]

            def on_startup(self, server) -> None:
                results.append("startup")

            def on_store(self, document: Dict[str, Any]) -> Dict[str, Any]:
                results.append("store")
                return {**document, "enriched": True}

            def on_shutdown(self) -> None:
                results.append("shutdown")

        # Create and register plugin
        registry = PluginRegistry()
        plugin = SamplePlugin()
        registry.register(plugin)

        # Test plugin info
        assert plugin.name == "sample"
        assert plugin.version == "1.2.3"
        assert plugin.description == "A sample plugin for testing"

        # Test tools registered
        assert registry.get_tool("sample:echo") is not None
        assert registry.get_tool("sample:uppercase") is not None

        # Test tool schemas
        schemas = registry.get_all_tool_schemas()
        assert len(schemas) == 2
        assert any(s["name"] == "echo" for s in schemas)
        assert any(s["name"] == "uppercase" for s in schemas)

        # Test tool calls
        echo_result = registry.handle_tool_call("sample:echo", {"message": "hello"})
        assert echo_result == {"echo": "hello"}

        upper_result = registry.handle_tool_call("sample:uppercase", {"text": "hello"})
        assert upper_result == {"result": "HELLO"}

        # Test hooks
        plugin.on_startup(None)
        doc = registry.call_hook("on_store", {"content": "test"})
        assert doc["enriched"] is True
        plugin.on_shutdown()

        assert results == ["startup", "store", "shutdown"]

        # Test unregister
        registry.unregister("sample")
        assert registry.get_plugin("sample") is None
        assert registry.get_tool("sample:echo") is None

        # Test stats
        stats = registry.get_stats()
        assert stats["plugin_count"] == 0
        assert stats["tool_count"] == 0


class TestPluginSecurity:
    """Tests for plugin security features."""

    def test_unapproved_plugin_blocked(self):
        """Test that unapproved plugins are blocked by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            (plugin_dir / "test_plugin.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class TestPlugin(MemoryPlugin):
    @property
    def name(self):
        return "test"

plugin = TestPlugin()
""")

            # Without unsafe_mode, plugin should not load
            registry = load_plugins(plugin_dir, unsafe_mode=False)
            assert registry.get_plugin("test") is None

    def test_approve_and_load_plugin(self):
        """Test approving a plugin allows it to load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            plugin_path = plugin_dir / "approved_plugin.py"

            plugin_path.write_text("""
from memory_mcp.plugins import MemoryPlugin

class ApprovedPlugin(MemoryPlugin):
    @property
    def name(self):
        return "approved"

plugin = ApprovedPlugin()
""")

            # Approve the plugin
            entry = approve_plugin(plugin_path, description="Test approval")
            assert "hash" in entry
            assert entry["hash"].startswith("sha256:")

            # Now it should load
            registry = load_plugins(plugin_dir, unsafe_mode=False)
            assert registry.get_plugin("approved") is not None

    def test_revoke_plugin(self):
        """Test revoking a plugin removes it from allowlist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            plugin_path = plugin_dir / "to_revoke.py"

            plugin_path.write_text("""
from memory_mcp.plugins import MemoryPlugin

class ToRevokePlugin(MemoryPlugin):
    @property
    def name(self):
        return "to_revoke"

plugin = ToRevokePlugin()
""")

            # Approve then revoke
            approve_plugin(plugin_path)
            result = revoke_plugin("to_revoke.py", plugin_dir)
            assert result is True

            # Should no longer load
            registry = load_plugins(plugin_dir, unsafe_mode=False)
            assert registry.get_plugin("to_revoke") is None

    def test_modified_plugin_blocked(self):
        """Test that modified plugins are blocked even if previously approved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            plugin_path = plugin_dir / "modified_plugin.py"

            # Create and approve original
            plugin_path.write_text("""
from memory_mcp.plugins import MemoryPlugin

class ModifiedPlugin(MemoryPlugin):
    @property
    def name(self):
        return "modified"

plugin = ModifiedPlugin()
""")
            approve_plugin(plugin_path)

            # Modify the plugin
            plugin_path.write_text("""
from memory_mcp.plugins import MemoryPlugin

class ModifiedPlugin(MemoryPlugin):
    @property
    def name(self):
        return "modified_EVIL"  # Changed!

plugin = ModifiedPlugin()
""")

            # Should be blocked due to hash mismatch
            registry = load_plugins(plugin_dir, unsafe_mode=False)
            assert registry.get_plugin("modified") is None
            assert registry.get_plugin("modified_EVIL") is None

    def test_list_plugins(self):
        """Test listing plugins with approval status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            # Create approved plugin
            approved_path = plugin_dir / "approved.py"
            approved_path.write_text("""
from memory_mcp.plugins import MemoryPlugin

class ApprovedPlugin(MemoryPlugin):
    @property
    def name(self):
        return "approved"

plugin = ApprovedPlugin()
""")
            approve_plugin(approved_path)

            # Create unapproved plugin
            (plugin_dir / "unapproved.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class UnapprovedPlugin(MemoryPlugin):
    @property
    def name(self):
        return "unapproved"

plugin = UnapprovedPlugin()
""")

            plugins = list_plugins(plugin_dir)
            assert len(plugins) == 2

            approved_info = next(p for p in plugins if p["name"] == "approved.py")
            unapproved_info = next(p for p in plugins if p["name"] == "unapproved.py")

            assert approved_info["approved"] is True
            assert unapproved_info["approved"] is False

    def test_verify_plugin_raises_on_invalid(self):
        """Test verify_plugin raises PluginSecurityError for unapproved plugins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            plugin_path = plugin_dir / "unapproved.py"
            plugin_path.write_text("# test")

            allowlist = {"plugins": {}}

            with pytest.raises(PluginSecurityError):
                verify_plugin(plugin_path, allowlist, unsafe_mode=False)

    def test_unsafe_mode_env_var(self):
        """Test MEMORY_MCP_PLUGINS_UNSAFE environment variable."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)

            (plugin_dir / "env_test.py").write_text("""
from memory_mcp.plugins import MemoryPlugin

class EnvTestPlugin(MemoryPlugin):
    @property
    def name(self):
        return "env_test"

plugin = EnvTestPlugin()
""")

            # Set env var
            os.environ["MEMORY_MCP_PLUGINS_UNSAFE"] = "1"
            try:
                registry = load_plugins(plugin_dir)
                assert registry.get_plugin("env_test") is not None
            finally:
                del os.environ["MEMORY_MCP_PLUGINS_UNSAFE"]
