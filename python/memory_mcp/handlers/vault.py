# handlers/vault.py
# Vault operations handler (write, read)

import logging
from typing import Dict, Any

from .base import BaseHandler
from ..validation import validate_string, validate_list

logger = logging.getLogger("memory_mcp")

# Valid vault folders
VALID_FOLDERS = ["code", "notes", "conversations", "references", "daily"]


class VaultHandler(BaseHandler):
    """Handler for Obsidian vault operations."""

    def write(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write to vault.

        Args:
            args: Dict containing:
                - path (required): Note path (without .md extension)
                - content (required): Note content
                - tags (optional): List of tags
                - folder (optional): Folder name (code, notes, conversations, references, daily)

        Returns:
            Dict with path and written status
        """
        path = validate_string(args.get("path"), "path", min_len=1, max_len=500)
        content = validate_string(args.get("content"), "content", min_len=0)
        tags = validate_list(args.get("tags"), "tags", str)
        folder = args.get("folder", "notes")

        if folder not in VALID_FOLDERS:
            raise ValueError(f"Invalid folder: {folder}. Must be one of: {', '.join(VALID_FOLDERS)}")

        logger.debug(f"Writing to vault: {folder}/{path}")

        frontmatter = {"tags": tags}

        note = self.vault.write_note(
            path,
            content,
            frontmatter,
            folder=folder
        )

        logger.info(f"Vault note written: {note.path}")
        return {"path": note.path, "written": True}

    def read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read from vault.

        Args:
            args: Dict containing:
                - path (required): Note path to read

        Returns:
            Dict with note details or found=False
        """
        path = validate_string(args.get("path"), "path", min_len=1, max_len=500)
        logger.debug(f"Reading from vault: {path}")

        note = self.vault.read_note(path)
        if not note:
            logger.debug(f"Vault note not found: {path}")
            return {"found": False, "path": path}

        logger.debug(f"Vault note found: {path}")
        return {
            "found": True,
            "path": note.path,
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "links": note.links,
            "modified_at": note.modified_at
        }
