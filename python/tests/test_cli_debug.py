"""
Tests for the CLI Debug Client.

Tests the interactive REPL functionality, command parsing,
and output formatting.
"""

import io
import json
import pytest
from unittest.mock import MagicMock, patch
import sys

from memory_mcp.cli_debug import MemoryMCPDebugCLI, Colors, main


class TestColorsClass:
    """Test the Colors utility class."""

    def test_colors_have_ansi_codes(self):
        """Test that colors have ANSI escape codes."""
        assert '\033[' in Colors.RED
        assert '\033[' in Colors.GREEN
        assert '\033[' in Colors.RESET

    def test_colors_disable(self):
        """Test that colors can be disabled."""
        # Store original values
        original_red = Colors.RED

        Colors.disable()

        assert Colors.RED == ''
        assert Colors.GREEN == ''
        assert Colors.RESET == ''

        # Restore (for other tests)
        Colors.RED = '\033[31m'
        Colors.GREEN = '\033[32m'
        Colors.RESET = '\033[0m'


class TestCLIParsing:
    """Test argument parsing functionality."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance with mocked server."""
        mock_server = MagicMock()
        mock_server.handle_call_tool.return_value = {
            "content": [{"text": '{"success": true}', "type": "text"}]
        }
        return MemoryMCPDebugCLI(server=mock_server)

    def test_parse_simple_args(self, cli):
        """Test parsing simple positional arguments."""
        positional, kwargs = cli._parse_kv_args("hello world test")
        assert positional == ["hello", "world", "test"]
        assert kwargs == {}

    def test_parse_kwargs(self, cli):
        """Test parsing keyword arguments."""
        positional, kwargs = cli._parse_kv_args("--type code --limit 10")
        assert positional == []
        assert kwargs == {"type": "code", "limit": "10"}

    def test_parse_mixed_args(self, cli):
        """Test parsing mixed positional and keyword arguments."""
        positional, kwargs = cli._parse_kv_args("query text --type hybrid --limit 5")
        assert positional == ["query", "text"]
        assert kwargs == {"type": "hybrid", "limit": "5"}

    def test_parse_boolean_flag(self, cli):
        """Test parsing boolean flags without values."""
        positional, kwargs = cli._parse_kv_args("content --verbose")
        assert positional == ["content"]
        assert kwargs == {"verbose": True}


class TestCLICommands:
    """Test CLI command execution."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance with mocked server."""
        mock_server = MagicMock()
        return MemoryMCPDebugCLI(server=mock_server)

    @pytest.fixture
    def cli_with_capture(self, cli):
        """CLI with stdout captured."""
        captured_output = io.StringIO()
        return cli, captured_output

    def test_store_command(self, cli):
        """Test store command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"id": "test-123"}', "type": "text"}]
        }

        cli.do_store('"test content" note test.py')

        cli.server.handle_call_tool.assert_called_once()
        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_store"
        assert call_args[0][1]["content"] == "test content"
        assert call_args[0][1]["type"] == "note"
        assert call_args[0][1]["source"] == "test.py"

    def test_store_with_tags(self, cli):
        """Test store command with tags."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"id": "test-123"}', "type": "text"}]
        }

        cli.do_store('"content" code src.py --tags python,test')

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][1]["tags"] == ["python", "test"]

    def test_search_command(self, cli):
        """Test search command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"results": []}', "type": "text"}]
        }

        cli.do_search("hello world --type hybrid --limit 5")

        cli.server.handle_call_tool.assert_called_once()
        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_search"
        assert call_args[0][1]["query"] == "hello world"
        assert call_args[0][1]["type"] == "hybrid"
        assert call_args[0][1]["limit"] == 5

    def test_recall_command(self, cli):
        """Test recall command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"id": "test-123", "content": "data"}', "type": "text"}]
        }

        cli.do_recall("test-123")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_recall"
        assert call_args[0][1]["id"] == "test-123"

    def test_delete_command(self, cli):
        """Test delete command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"deleted": true}', "type": "text"}]
        }

        cli.do_delete("test-123")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_delete"
        assert call_args[0][1]["id"] == "test-123"

    def test_list_command(self, cli):
        """Test list command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"items": []}', "type": "text"}]
        }

        cli.do_list("--type code --limit 10")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_list"
        assert call_args[0][1]["type"] == "code"
        assert call_args[0][1]["limit"] == 10

    def test_stats_command(self, cli):
        """Test stats command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"sqlite_count": 100}', "type": "text"}]
        }

        cli.do_stats("")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "memory_stats"

    def test_session_save_command(self, cli):
        """Test session_save command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"session_id": "sess-123"}', "type": "text"}]
        }

        cli.do_session_save("/path/to/project --files file1.py,file2.py")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "session_save"
        assert call_args[0][1]["project_path"] == "/path/to/project"
        assert call_args[0][1]["active_files"] == ["file1.py", "file2.py"]

    def test_vault_write_command(self, cli):
        """Test vault_write command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"path": "test.md"}', "type": "text"}]
        }

        cli.do_vault_write('test "test content" --folder notes')

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "vault_write"
        assert call_args[0][1]["path"] == "test"
        assert call_args[0][1]["content"] == "test content"
        assert call_args[0][1]["folder"] == "notes"

    def test_vault_read_command(self, cli):
        """Test vault_read command calls correct tool."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"content": "file contents"}', "type": "text"}]
        }

        cli.do_vault_read("notes/test.md")

        call_args = cli.server.handle_call_tool.call_args
        assert call_args[0][0] == "vault_read"
        assert call_args[0][1]["path"] == "notes/test.md"


class TestCLIOutput:
    """Test CLI output formatting."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance with mocked server."""
        mock_server = MagicMock()
        cli = MemoryMCPDebugCLI(server=mock_server)
        cli.timing_enabled = False  # Disable timing for cleaner test output
        return cli

    def test_print_success_result(self, cli, capsys):
        """Test successful result printing."""
        result = {
            "content": [{"text": '{"id": "test-123"}', "type": "text"}]
        }

        cli._print_result(result)

        captured = capsys.readouterr()
        assert "Success" in captured.out or "✓" in captured.out
        assert "test-123" in captured.out

    def test_print_error_result(self, cli, capsys):
        """Test error result printing."""
        result = {
            "isError": True,
            "content": [{"text": "Something went wrong", "type": "text"}]
        }

        cli._print_result(result)

        captured = capsys.readouterr()
        assert "Error" in captured.out or "✗" in captured.out
        assert "Something went wrong" in captured.out


class TestCLIHealth:
    """Test the health command."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance with mocked server."""
        mock_server = MagicMock()
        cli = MemoryMCPDebugCLI(server=mock_server)
        cli.timing_enabled = False
        return cli

    def test_health_command_success(self, cli, capsys):
        """Test health command with all components available."""
        cli.server.handle_call_tool.return_value = {
            "content": [{
                "text": json.dumps({
                    "sqlite_count": 100,
                    "components": {
                        "sqlite": True,
                        "vault": True,
                        "redis": True,
                        "faiss": True,
                        "embedder": True
                    },
                    "redis": {"cache_hits": 50, "cache_misses": 5},
                    "faiss": {"total_vectors": 1000},
                    "embedder": {"provider": "local/test"}
                }),
                "type": "text"
            }]
        }

        cli.do_health("")

        captured = capsys.readouterr()
        assert "SQLite" in captured.out
        assert "100" in captured.out
        assert "Vault" in captured.out
        assert "Redis" in captured.out
        assert "Graphiti" in captured.out
        assert "Core components healthy" in captured.out

    def test_health_command_partial(self, cli, capsys):
        """Test health command with some components unavailable."""
        cli.server.handle_call_tool.return_value = {
            "content": [{
                "text": json.dumps({
                    "sqlite_count": 50,
                    "components": {
                        "sqlite": True,
                        "vault": True,
                        "redis": False,
                        "graphiti": False,
                        "livegrep": False,
                        "embedder": False
                    }
                }),
                "type": "text"
            }]
        }

        cli.do_health("")

        captured = capsys.readouterr()
        assert "SQLite" in captured.out
        assert "Not available" in captured.out or "optional" in captured.out.lower()


class TestCLIToggleCommands:
    """Test toggle commands."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance."""
        mock_server = MagicMock()
        return MemoryMCPDebugCLI(server=mock_server)

    def test_timing_toggle(self, cli, capsys):
        """Test timing toggle command."""
        original = cli.timing_enabled

        cli.do_timing("off")
        assert cli.timing_enabled is False

        cli.do_timing("on")
        assert cli.timing_enabled is True

        cli.do_timing("")  # Toggle
        assert cli.timing_enabled is False

    def test_verbose_toggle(self, cli, capsys):
        """Test verbose toggle command."""
        original = cli.verbose

        cli.do_verbose("on")
        assert cli.verbose is True

        cli.do_verbose("off")
        assert cli.verbose is False

        cli.do_verbose("")  # Toggle
        assert cli.verbose is True


class TestCLIExitCommands:
    """Test exit/quit commands."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance."""
        mock_server = MagicMock()
        return MemoryMCPDebugCLI(server=mock_server)

    def test_exit_returns_true(self, cli):
        """Test exit command returns True to stop loop."""
        result = cli.do_exit("")
        assert result is True

    def test_quit_returns_true(self, cli):
        """Test quit command returns True to stop loop."""
        result = cli.do_quit("")
        assert result is True

    def test_eof_returns_true(self, cli):
        """Test EOF (Ctrl+D) returns True to stop loop."""
        result = cli.do_EOF("")
        assert result is True


class TestCLILastCommand:
    """Test the last command."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance."""
        mock_server = MagicMock()
        return MemoryMCPDebugCLI(server=mock_server)

    def test_last_shows_previous_result(self, cli, capsys):
        """Test last command shows previous result."""
        cli.last_result = {
            "content": [{"text": '{"id": "previous-123"}', "type": "text"}]
        }
        cli.timing_enabled = False

        cli.do_last("")

        captured = capsys.readouterr()
        assert "previous-123" in captured.out

    def test_last_with_no_result(self, cli, capsys):
        """Test last command when no previous result."""
        cli.last_result = None

        cli.do_last("")

        captured = capsys.readouterr()
        assert "No previous result" in captured.out


class TestCLICallTool:
    """Test the _call_tool method."""

    @pytest.fixture
    def cli(self, test_config):
        """Create a CLI instance."""
        mock_server = MagicMock()
        cli = MemoryMCPDebugCLI(server=mock_server)
        cli.timing_enabled = False
        return cli

    def test_call_tool_success(self, cli):
        """Test successful tool call."""
        cli.server.handle_call_tool.return_value = {
            "content": [{"text": '{"success": true}', "type": "text"}]
        }

        result = cli._call_tool("memory_stats", {})

        assert result["content"][0]["text"] == '{"success": true}'
        assert cli.last_result == result

    def test_call_tool_error(self, cli, capsys):
        """Test tool call with exception."""
        cli.server.handle_call_tool.side_effect = Exception("Test error")

        result = cli._call_tool("memory_stats", {})

        assert result["isError"] is True
        captured = capsys.readouterr()
        assert "Test error" in captured.out


class TestCLIMain:
    """Test the main entry point."""

    def test_main_creates_cli(self):
        """Test main function creates CLI instance."""
        with patch.object(MemoryMCPDebugCLI, 'cmdloop') as mock_loop:
            with patch('sys.stdin') as mock_stdin:
                mock_stdin.isatty.return_value = True
                main()
                mock_loop.assert_called_once()
