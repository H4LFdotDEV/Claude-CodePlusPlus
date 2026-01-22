#!/usr/bin/env python3
"""
CLI Debug Client for Memory MCP Server.

Interactive REPL for testing and debugging MCP tool invocations.
Provides pretty-printed responses, timing info, and error tracebacks.

Usage:
    python -m memory_mcp.cli_debug

Commands:
    store <content> <type> <source> [--tags tag1,tag2] [--project name]
    search <query> [--type text|semantic|hybrid] [--limit N]
    recall <id>
    delete <id>
    list [--type <type>] [--limit N]
    session_save <project_path> [--files file1,file2]
    session_restore [--session_id <id>]
    vault_write <path> <content> [--folder code|notes]
    vault_read <path>
    stats
    health
    help
    exit
"""

import cmd
import json
import sys
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from .server import MemoryMCPServer
    from .config import get_config
except ImportError:
    # Allow running as standalone script
    from memory_mcp.server import MemoryMCPServer
    from memory_mcp.config import get_config


class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Text colors
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_CYAN = '\033[96m'

    @classmethod
    def disable(cls):
        """Disable all colors (for non-TTY output)."""
        for attr in dir(cls):
            if not attr.startswith('_') and attr.isupper():
                setattr(cls, attr, '')


class MemoryMCPDebugCLI(cmd.Cmd):
    """Interactive CLI for debugging Memory MCP tools."""

    intro = f"""{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║           Memory MCP Debug Client v1.0                       ║
║           Type 'help' for commands, 'exit' to quit           ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    prompt = f'{Colors.GREEN}mcp>{Colors.RESET} '

    def __init__(self, server: Optional[MemoryMCPServer] = None):
        super().__init__()
        self.server = server or MemoryMCPServer(config=get_config())
        self.last_result: Optional[Dict] = None
        self.timing_enabled = True
        self.verbose = False

        # Disable colors if not a TTY
        if not sys.stdout.isatty():
            Colors.disable()
            self.intro = "Memory MCP Debug Client v1.0\nType 'help' for commands, 'exit' to quit\n"
            self.prompt = 'mcp> '

    def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict:
        """Call an MCP tool and return the result with timing."""
        start_time = time.time()

        try:
            result = self.server.handle_call_tool(tool_name, args)
            elapsed_ms = (time.time() - start_time) * 1000

            self.last_result = result

            if self.timing_enabled:
                print(f"{Colors.DIM}[{elapsed_ms:.2f}ms]{Colors.RESET}")

            return result

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            if self.timing_enabled:
                print(f"{Colors.DIM}[{elapsed_ms:.2f}ms]{Colors.RESET}")

            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            if self.verbose:
                traceback.print_exc()
            return {"isError": True, "error": str(e)}

    def _print_result(self, result: Dict):
        """Pretty-print a tool result."""
        if result.get("isError"):
            print(f"{Colors.RED}✗ Error:{Colors.RESET}")
            if "content" in result:
                for item in result["content"]:
                    print(f"  {Colors.RED}{item.get('text', str(item))}{Colors.RESET}")
            elif "error" in result:
                print(f"  {Colors.RED}{result['error']}{Colors.RESET}")
            return

        print(f"{Colors.GREEN}✓ Success:{Colors.RESET}")

        if "content" not in result:
            print(json.dumps(result, indent=2, default=str))
            return

        for item in result["content"]:
            text = item.get("text", "")
            try:
                # Try to parse as JSON for pretty printing
                data = json.loads(text)
                print(json.dumps(data, indent=2, default=str))
            except json.JSONDecodeError:
                print(text)

    def _parse_kv_args(self, args: str) -> tuple[list, dict]:
        """Parse positional and keyword arguments from a string.

        Example: 'content note source --tags tag1,tag2 --project test'
        Returns: (['content', 'note', 'source'], {'tags': 'tag1,tag2', 'project': 'test'})
        """
        parts = args.split()
        positional = []
        kwargs = {}

        i = 0
        while i < len(parts):
            if parts[i].startswith('--'):
                key = parts[i][2:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                    kwargs[key] = parts[i + 1]
                    i += 2
                else:
                    kwargs[key] = True
                    i += 1
            else:
                positional.append(parts[i])
                i += 1

        return positional, kwargs

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def do_store(self, arg: str):
        """Store content in memory.

        Usage: store <content> <type> <source> [--tags tag1,tag2] [--project name]

        Types: code, note, conversation, reference

        Example:
            store "def hello(): print('hi')" code example.py --tags python,function
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: store <content> <type> <source> [--tags] [--project]{Colors.RESET}")
            return

        # Handle quoted content
        if arg.startswith('"'):
            end_quote = arg.find('"', 1)
            if end_quote != -1:
                content = arg[1:end_quote]
                remaining = arg[end_quote + 1:].strip()
            else:
                content = arg[1:]
                remaining = ""
        else:
            parts = arg.split(None, 1)
            content = parts[0]
            remaining = parts[1] if len(parts) > 1 else ""

        positional, kwargs = self._parse_kv_args(remaining)

        if len(positional) < 2:
            print(f"{Colors.YELLOW}Usage: store <content> <type> <source>{Colors.RESET}")
            return

        args = {
            "content": content,
            "type": positional[0],
            "source": positional[1],
        }

        if "tags" in kwargs:
            args["tags"] = kwargs["tags"].split(",")
        if "project" in kwargs:
            args["project"] = kwargs["project"]

        result = self._call_tool("memory_store", args)
        self._print_result(result)

    def do_search(self, arg: str):
        """Search memory.

        Usage: search <query> [--type text|semantic|hybrid] [--limit N]

        Example:
            search "hello world" --type hybrid --limit 5
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: search <query> [--type] [--limit]{Colors.RESET}")
            return

        positional, kwargs = self._parse_kv_args(arg)

        if not positional:
            print(f"{Colors.YELLOW}Usage: search <query>{Colors.RESET}")
            return

        args = {"query": " ".join(positional)}

        if "type" in kwargs:
            args["type"] = kwargs["type"]
        if "limit" in kwargs:
            args["limit"] = int(kwargs["limit"])

        result = self._call_tool("memory_search", args)
        self._print_result(result)

    def do_recall(self, arg: str):
        """Recall a specific memory by ID.

        Usage: recall <document_id>
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: recall <document_id>{Colors.RESET}")
            return

        result = self._call_tool("memory_recall", {"id": arg.strip()})
        self._print_result(result)

    def do_delete(self, arg: str):
        """Delete a memory by ID.

        Usage: delete <document_id>
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: delete <document_id>{Colors.RESET}")
            return

        result = self._call_tool("memory_delete", {"id": arg.strip()})
        self._print_result(result)

    def do_list(self, arg: str):
        """List recent memories.

        Usage: list [--type code|note|conversation|reference] [--limit N] [--project name]
        """
        _, kwargs = self._parse_kv_args(arg)

        args = {}
        if "type" in kwargs:
            args["type"] = kwargs["type"]
        if "limit" in kwargs:
            args["limit"] = int(kwargs["limit"])
        if "project" in kwargs:
            args["project"] = kwargs["project"]

        result = self._call_tool("memory_list", args)
        self._print_result(result)

    def do_session_save(self, arg: str):
        """Save current session state.

        Usage: session_save <project_path> [--files file1,file2] [--context key=value]
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: session_save <project_path>{Colors.RESET}")
            return

        positional, kwargs = self._parse_kv_args(arg)

        if not positional:
            print(f"{Colors.YELLOW}Usage: session_save <project_path>{Colors.RESET}")
            return

        args = {"project_path": positional[0]}

        if "files" in kwargs:
            args["active_files"] = kwargs["files"].split(",")
        if "context" in kwargs:
            # Parse key=value pairs
            ctx = {}
            for pair in kwargs["context"].split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    ctx[k] = v
            args["context"] = ctx

        result = self._call_tool("session_save", args)
        self._print_result(result)

    def do_session_restore(self, arg: str):
        """Restore a previous session.

        Usage: session_restore [--session_id <id>]
        """
        _, kwargs = self._parse_kv_args(arg)

        args = {}
        if "session_id" in kwargs:
            args["session_id"] = kwargs["session_id"]

        result = self._call_tool("session_restore", args)
        self._print_result(result)

    def do_vault_write(self, arg: str):
        """Write to Obsidian vault.

        Usage: vault_write <path> "<content>" [--folder code|notes|conversations|references|daily] [--tags tag1,tag2]
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: vault_write <path> <content> [--folder] [--tags]{Colors.RESET}")
            return

        # Parse path and content
        parts = arg.split(None, 1)
        if len(parts) < 2:
            print(f"{Colors.YELLOW}Usage: vault_write <path> <content>{Colors.RESET}")
            return

        path = parts[0]
        remaining = parts[1]

        # Handle quoted content
        if remaining.startswith('"'):
            end_quote = remaining.find('"', 1)
            if end_quote != -1:
                content = remaining[1:end_quote]
                options = remaining[end_quote + 1:].strip()
            else:
                content = remaining[1:]
                options = ""
        else:
            content_parts = remaining.split(None, 1)
            content = content_parts[0]
            options = content_parts[1] if len(content_parts) > 1 else ""

        _, kwargs = self._parse_kv_args(options)

        args = {"path": path, "content": content}

        if "folder" in kwargs:
            args["folder"] = kwargs["folder"]
        if "tags" in kwargs:
            args["tags"] = kwargs["tags"].split(",")

        result = self._call_tool("vault_write", args)
        self._print_result(result)

    def do_vault_read(self, arg: str):
        """Read from Obsidian vault.

        Usage: vault_read <path>
        """
        if not arg.strip():
            print(f"{Colors.YELLOW}Usage: vault_read <path>{Colors.RESET}")
            return

        result = self._call_tool("vault_read", {"path": arg.strip()})
        self._print_result(result)

    def do_stats(self, arg: str):
        """Get memory system statistics.

        Usage: stats
        """
        result = self._call_tool("memory_stats", {})
        self._print_result(result)

    def do_health(self, arg: str):
        """Check system health status.

        Usage: health

        Performs health checks on all components and displays status.
        """
        print(f"{Colors.CYAN}╔═══════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║          System Health Check              ║{Colors.RESET}")
        print(f"{Colors.CYAN}╚═══════════════════════════════════════════╝{Colors.RESET}")
        print()

        # Get stats which includes component info
        result = self._call_tool("memory_stats", {})

        if result.get("isError"):
            print(f"{Colors.RED}✗ Health check failed{Colors.RESET}")
            self._print_result(result)
            return

        try:
            data = json.loads(result["content"][0]["text"])

            components = data.get("components", {})

            # SQLite
            sqlite_ok = components.get("sqlite", False)
            sqlite_count = data.get("sqlite_count", 0)
            status = f"{Colors.GREEN}✓{Colors.RESET}" if sqlite_ok else f"{Colors.RED}✗{Colors.RESET}"
            print(f"  {status} SQLite: {sqlite_count} documents")

            # Vault
            vault_ok = components.get("vault", False)
            status = f"{Colors.GREEN}✓{Colors.RESET}" if vault_ok else f"{Colors.RED}✗{Colors.RESET}"
            print(f"  {status} Vault: {'Connected' if vault_ok else 'Not available'}")

            # Redis
            redis_ok = components.get("redis", False)
            status = f"{Colors.GREEN}✓{Colors.RESET}" if redis_ok else f"{Colors.YELLOW}○{Colors.RESET}"
            redis_info = ""
            if redis_ok and "redis" in data:
                redis_stats = data["redis"]
                if isinstance(redis_stats, dict):
                    hits = redis_stats.get("cache_hits", 0)
                    misses = redis_stats.get("cache_misses", 0)
                    redis_info = f" (hits: {hits}, misses: {misses})"
            print(f"  {status} Redis: {'Connected' + redis_info if redis_ok else 'Not available (optional)'}")

            # FAISS
            faiss_ok = components.get("faiss", False)
            status = f"{Colors.GREEN}✓{Colors.RESET}" if faiss_ok else f"{Colors.YELLOW}○{Colors.RESET}"
            faiss_info = ""
            if faiss_ok and "faiss" in data:
                vectors = data["faiss"].get("total_vectors", 0)
                faiss_info = f" ({vectors} vectors)"
            print(f"  {status} FAISS: {'Initialized' + faiss_info if faiss_ok else 'Not available (optional)'}")

            # Embedder
            embedder_ok = components.get("embedder", False)
            status = f"{Colors.GREEN}✓{Colors.RESET}" if embedder_ok else f"{Colors.YELLOW}○{Colors.RESET}"
            embedder_info = ""
            if embedder_ok and "embedder" in data:
                provider = data["embedder"].get("provider", "unknown")
                embedder_info = f" ({provider})"
            print(f"  {status} Embedder: {'Active' + embedder_info if embedder_ok else 'Not available (optional)'}")

            print()

            # Summary
            core_ok = sqlite_ok and vault_ok
            if core_ok:
                print(f"{Colors.GREEN}Core components healthy ✓{Colors.RESET}")
            else:
                print(f"{Colors.RED}Core components unhealthy ✗{Colors.RESET}")

        except Exception as e:
            print(f"{Colors.RED}Error parsing stats: {e}{Colors.RESET}")
            self._print_result(result)

    def do_timing(self, arg: str):
        """Toggle timing display.

        Usage: timing [on|off]
        """
        if arg.strip().lower() == "on":
            self.timing_enabled = True
        elif arg.strip().lower() == "off":
            self.timing_enabled = False
        else:
            self.timing_enabled = not self.timing_enabled

        status = "enabled" if self.timing_enabled else "disabled"
        print(f"Timing {status}")

    def do_verbose(self, arg: str):
        """Toggle verbose mode (show full tracebacks).

        Usage: verbose [on|off]
        """
        if arg.strip().lower() == "on":
            self.verbose = True
        elif arg.strip().lower() == "off":
            self.verbose = False
        else:
            self.verbose = not self.verbose

        status = "enabled" if self.verbose else "disabled"
        print(f"Verbose mode {status}")

    def do_last(self, arg: str):
        """Show the last result.

        Usage: last
        """
        if self.last_result:
            self._print_result(self.last_result)
        else:
            print("No previous result")

    def do_exit(self, arg: str):
        """Exit the CLI."""
        print(f"{Colors.CYAN}Goodbye!{Colors.RESET}")
        return True

    def do_quit(self, arg: str):
        """Exit the CLI (alias for exit)."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str):
        """Exit on Ctrl+D."""
        print()
        return self.do_exit(arg)

    def emptyline(self):
        """Do nothing on empty line."""
        pass

    def default(self, line: str):
        """Handle unknown commands."""
        print(f"{Colors.YELLOW}Unknown command: {line}{Colors.RESET}")
        print("Type 'help' for available commands")


def main():
    """Main entry point for the CLI."""
    cli = MemoryMCPDebugCLI()

    # Check for non-interactive mode (piped input)
    if not sys.stdin.isatty():
        # Process commands from stdin without prompt
        cli.prompt = ''
        cli.intro = ''

    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}Interrupted. Goodbye!{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
