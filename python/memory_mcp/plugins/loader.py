"""Plugin loader for discovering and loading plugins.

SECURITY NOTE: Plugins execute arbitrary Python code with full process privileges.
By default, plugins require explicit approval via SHA-256 hash allowlist.
Set MEMORY_MCP_PLUGINS_UNSAFE=1 to disable verification (NOT RECOMMENDED).
"""

import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Optional, Set

from .base import MemoryPlugin
from .registry import PluginRegistry

logger = logging.getLogger(__name__)

DEFAULT_PLUGIN_DIR = "~/.claude-code-pp/plugins"
ALLOWLIST_FILE = "allowed_plugins.json"


class PluginSecurityError(Exception):
    """Raised when a plugin fails security verification."""
    pass


def _compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _load_allowlist(plugin_dir: Path) -> dict:
    """Load the plugin allowlist from the plugin directory.

    The allowlist file format:
    {
        "plugins": {
            "plugin_name.py": {
                "hash": "sha256:abc123...",
                "approved_by": "user",
                "approved_at": "2024-01-01T00:00:00Z",
                "description": "Optional description"
            }
        },
        "allow_unsigned": false
    }
    """
    allowlist_path = plugin_dir / ALLOWLIST_FILE
    if not allowlist_path.exists():
        return {"plugins": {}, "allow_unsigned": False}

    try:
        with open(allowlist_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load plugin allowlist: {e}")
        return {"plugins": {}, "allow_unsigned": False}


def _save_allowlist(plugin_dir: Path, allowlist: dict) -> None:
    """Save the plugin allowlist."""
    allowlist_path = plugin_dir / ALLOWLIST_FILE
    with open(allowlist_path, "w") as f:
        json.dump(allowlist, f, indent=2)


def verify_plugin(path: Path, allowlist: dict, unsafe_mode: bool = False) -> bool:
    """Verify a plugin against the allowlist.

    Args:
        path: Path to the plugin file
        allowlist: Loaded allowlist dictionary
        unsafe_mode: If True, skip verification (dangerous!)

    Returns:
        True if plugin is allowed to load

    Raises:
        PluginSecurityError: If plugin verification fails
    """
    if unsafe_mode:
        logger.warning(f"UNSAFE MODE: Loading unverified plugin {path.name}")
        return True

    plugin_name = path.name
    file_hash = _compute_file_hash(path)

    # Check if plugin is in allowlist
    if plugin_name not in allowlist.get("plugins", {}):
        raise PluginSecurityError(
            f"Plugin '{plugin_name}' not in allowlist. "
            f"To approve, run: memory-mcp plugin approve {path}"
        )

    # Verify hash matches
    expected_hash = allowlist["plugins"][plugin_name].get("hash", "")
    if not expected_hash.startswith("sha256:"):
        raise PluginSecurityError(
            f"Invalid hash format for plugin '{plugin_name}'"
        )

    expected_hash_value = expected_hash[7:]  # Remove "sha256:" prefix
    if file_hash != expected_hash_value:
        raise PluginSecurityError(
            f"Plugin '{plugin_name}' hash mismatch! "
            f"Expected: {expected_hash_value[:16]}..., "
            f"Got: {file_hash[:16]}... "
            f"Plugin may have been modified. Re-approve if intentional."
        )

    logger.info(f"Plugin '{plugin_name}' verified (hash: {file_hash[:16]}...)")
    return True


def approve_plugin(plugin_path: Path, description: str = "") -> dict:
    """Approve a plugin by adding it to the allowlist.

    Args:
        plugin_path: Path to the plugin file
        description: Optional description for the approval

    Returns:
        Updated allowlist entry
    """
    from datetime import datetime, timezone

    plugin_dir = plugin_path.parent
    allowlist = _load_allowlist(plugin_dir)

    file_hash = _compute_file_hash(plugin_path)

    entry = {
        "hash": f"sha256:{file_hash}",
        "approved_by": os.environ.get("USER", "unknown"),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "description": description,
    }

    allowlist["plugins"][plugin_path.name] = entry
    _save_allowlist(plugin_dir, allowlist)

    logger.info(f"Approved plugin '{plugin_path.name}' (hash: {file_hash[:16]}...)")
    return entry


def revoke_plugin(plugin_name: str, plugin_dir: Optional[Path] = None) -> bool:
    """Revoke a plugin's approval.

    Args:
        plugin_name: Name of the plugin file (e.g., "my_plugin.py")
        plugin_dir: Plugin directory (uses default if not specified)

    Returns:
        True if plugin was revoked, False if not found
    """
    plugin_dir = plugin_dir or Path(os.path.expanduser(DEFAULT_PLUGIN_DIR))
    allowlist = _load_allowlist(plugin_dir)

    if plugin_name in allowlist.get("plugins", {}):
        del allowlist["plugins"][plugin_name]
        _save_allowlist(plugin_dir, allowlist)
        logger.info(f"Revoked plugin '{plugin_name}'")
        return True

    return False


def load_plugins(
    plugin_dir: Optional[Path] = None,
    registry: Optional[PluginRegistry] = None,
    unsafe_mode: Optional[bool] = None
) -> PluginRegistry:
    """Load plugins from directory and return registry.

    Args:
        plugin_dir: Directory containing plugin .py files
        registry: Existing registry to add to, or creates new one
        unsafe_mode: If True, skip security verification (uses env var if None)

    Returns:
        PluginRegistry with loaded plugins
    """
    # Check for unsafe mode from environment if not specified
    if unsafe_mode is None:
        unsafe_mode = os.environ.get("MEMORY_MCP_PLUGINS_UNSAFE", "").lower() in ("1", "true", "yes")

    if unsafe_mode:
        logger.warning(
            "SECURITY WARNING: Plugin verification disabled! "
            "Unset MEMORY_MCP_PLUGINS_UNSAFE to enable verification."
        )

    plugin_dir = plugin_dir or Path(os.path.expanduser(DEFAULT_PLUGIN_DIR))
    registry = registry or PluginRegistry()

    if not plugin_dir.exists():
        logger.debug(f"Plugin directory does not exist: {plugin_dir}")
        return registry

    # Load allowlist
    allowlist = _load_allowlist(plugin_dir)

    loaded_count = 0
    skipped_count = 0

    for path in plugin_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        if path.name == ALLOWLIST_FILE:
            continue

        try:
            # Verify plugin before loading
            verify_plugin(path, allowlist, unsafe_mode)

            # Load the plugin
            plugin = load_plugin_from_file(path)
            if plugin:
                registry.register(plugin)
                loaded_count += 1
                logger.info(f"Loaded plugin: {plugin.name} from {path.name}")
        except PluginSecurityError as e:
            logger.warning(f"Security: {e}")
            skipped_count += 1
        except Exception as e:
            logger.warning(f"Failed to load plugin {path}: {e}")
            skipped_count += 1

    if loaded_count > 0 or skipped_count > 0:
        logger.info(f"Plugin loading complete: {loaded_count} loaded, {skipped_count} skipped")

    return registry


def load_plugin_from_file(path: Path) -> Optional[MemoryPlugin]:
    """Load a single plugin from a Python file.

    The file should define a module-level `plugin` variable that is
    an instance of MemoryPlugin.

    WARNING: This executes arbitrary code. Always verify plugins before calling.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.warning(f"Error executing plugin module {path}: {e}")
        return None

    # Look for 'plugin' attribute
    if hasattr(module, "plugin"):
        plugin = module.plugin
        if isinstance(plugin, MemoryPlugin):
            return plugin
        else:
            logger.warning(
                f"Plugin {path}: 'plugin' is not a MemoryPlugin instance"
            )
    else:
        logger.debug(f"Plugin {path}: no 'plugin' attribute found")

    return None


def list_plugins(plugin_dir: Optional[Path] = None) -> list:
    """List all plugins and their approval status.

    Returns:
        List of dicts with plugin info
    """
    plugin_dir = plugin_dir or Path(os.path.expanduser(DEFAULT_PLUGIN_DIR))

    if not plugin_dir.exists():
        return []

    allowlist = _load_allowlist(plugin_dir)
    plugins = []

    for path in plugin_dir.glob("*.py"):
        if path.name.startswith("_") or path.name == ALLOWLIST_FILE:
            continue

        file_hash = _compute_file_hash(path)
        approved_entry = allowlist.get("plugins", {}).get(path.name, {})

        is_approved = False
        hash_matches = False

        if approved_entry:
            expected = approved_entry.get("hash", "")[7:]  # Remove "sha256:"
            hash_matches = (file_hash == expected)
            is_approved = hash_matches

        plugins.append({
            "name": path.name,
            "path": str(path),
            "hash": file_hash,
            "approved": is_approved,
            "hash_matches": hash_matches,
            "approved_at": approved_entry.get("approved_at"),
            "approved_by": approved_entry.get("approved_by"),
            "description": approved_entry.get("description"),
        })

    return plugins
