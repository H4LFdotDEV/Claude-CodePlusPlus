# vault_manager.py
# Obsidian-Compatible Markdown Vault for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Long-term storage layer - human-readable, searchable, version-controllable

import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import yaml

from .config import get_config, VaultConfig

logger = logging.getLogger("memory_mcp.vault_manager")


@dataclass
class VaultNote:
    """A note in the vault."""
    path: str  # Relative path within vault
    title: str
    content: str
    frontmatter: Dict[str, Any]
    links: List[str]  # Outgoing [[wikilinks]]
    tags: List[str]  # #tags in content
    created_at: str
    modified_at: str

    @property
    def id(self) -> str:
        """Generate ID from path."""
        return hashlib.sha256(self.path.encode()).hexdigest()[:16]


class VaultManager:
    """
    Manages an Obsidian-compatible markdown vault with path traversal protection.

    Security Properties:
    - All paths are validated against the vault root directory
    - Symlinks are fully resolved before validation
    - Works correctly on both case-sensitive and case-insensitive filesystems
    - Protects against: .. traversal, symlink escapes, null byte injection, case-based escapes

    Limitations:
    - Time-of-check-time-of-use (TOCTOU) race condition possible if vault root is
      moved/deleted between path validation and file operation. Acceptable for
      single-machine usage.
    - Relative symlinks created by users could potentially point outside vault
      (e.g., user creates vault/doc with symlink to external location).
      This is user-controlled risk, not vault-enforced escape.

    Filesystem Support:
    - Linux: Case-sensitive filesystems (ext4, etc.) - exact byte comparison
    - macOS: Case-insensitive filesystems (APFS) - case-normalized comparison
    - Windows: Case-insensitive filesystems (NTFS) - case-normalized comparison
    """

    # Obsidian-style folder structure
    FOLDER_CODE = "code"
    FOLDER_NOTES = "notes"
    FOLDER_CONVERSATIONS = "conversations"
    FOLDER_REFERENCES = "references"
    FOLDER_DAILY = "daily"
    FOLDER_TEMPLATES = "templates"

    def __init__(self, config: Optional[VaultConfig] = None, path: Optional[str] = None):
        self.config = config or get_config().vault
        self.path = path or self.config.path
        self.path = os.path.expanduser(self.path)
        self.obsidian_compatible = self.config.obsidian_compatible
        self._case_sensitivity_cache: Dict[str, bool] = {}

        self._init_vault()

    def _init_vault(self):
        """Initialize vault directory structure."""
        Path(self.path).mkdir(parents=True, exist_ok=True)

        # Create folder structure
        for folder in [
            self.FOLDER_CODE,
            self.FOLDER_NOTES,
            self.FOLDER_CONVERSATIONS,
            self.FOLDER_REFERENCES,
            self.FOLDER_DAILY,
            self.FOLDER_TEMPLATES
        ]:
            (Path(self.path) / folder).mkdir(exist_ok=True)

        # Create Obsidian config if compatible mode
        if self.obsidian_compatible:
            obsidian_dir = Path(self.path) / ".obsidian"
            obsidian_dir.mkdir(exist_ok=True)

            # Basic app config
            app_config = obsidian_dir / "app.json"
            if not app_config.exists():
                app_config.write_text('{"showLineNumber": true, "spellcheck": true}')

    def _is_case_sensitive_filesystem(self, path: str) -> bool:
        """
        Detect if filesystem is case-sensitive.

        Args:
            path: Filesystem path to check

        Returns:
            True if filesystem is case-sensitive, False otherwise.
        """
        # Check if we've already cached this result
        mount_point = path.split(os.sep)[0] or os.sep

        if mount_point in self._case_sensitivity_cache:
            return self._case_sensitivity_cache[mount_point]

        # Test by comparing paths at different cases
        test_dir = os.path.dirname(path)
        if not test_dir or not os.path.exists(test_dir):
            # Default to case-sensitive if we can't test
            result = True
        else:
            # Simple test: if lower and upper case paths resolve differently, it's case-sensitive
            test_lower = os.path.realpath(test_dir)
            test_upper = os.path.realpath(test_dir.upper())

            # On case-insensitive systems, these will be identical
            result = test_lower != test_upper

        self._case_sensitivity_cache[mount_point] = result
        return result

    def _full_path(self, relative_path: str) -> str:
        """
        Get full filesystem path with comprehensive path traversal protection.

        Resolves symlinks, normalizes case on case-insensitive filesystems,
        and validates path is within vault root.

        Args:
            relative_path: Relative path within vault (may contain ../, etc.)

        Returns:
            Absolute filesystem path within vault.

        Raises:
            ValueError: If path traversal, symlink escape, or other attacks detected.
            TypeError: If relative_path is not a string.
        """
        # Input validation
        if not isinstance(relative_path, str):
            raise TypeError(f"Path must be string, got {type(relative_path).__name__}")

        if not relative_path:
            raise ValueError("Path cannot be empty")

        # Detect null byte injection
        if '\x00' in relative_path:
            raise ValueError("Path contains null bytes (path injection detected)")

        # Normalize backslashes to forward slashes for cross-platform consistency
        # This prevents Windows-style path traversal attacks on Unix systems
        normalized_input = relative_path.replace("\\", "/")

        # Reject absolute paths (should be relative to vault)
        if normalized_input.startswith("/") or (
            len(normalized_input) > 1 and normalized_input[1] == ":"
        ):
            raise ValueError(
                f"Path must be relative to vault, not absolute: {relative_path}"
            )

        try:
            # Expand user home directory if present (after normalization)
            vault_root = os.path.expanduser(self.path)

            # Get real paths - resolves symlinks, .. sequences, and normalizes
            vault_real = os.path.realpath(vault_root)

            # Join paths and resolve to canonical form
            candidate_path = os.path.join(vault_real, normalized_input)
            candidate_real = os.path.realpath(candidate_path)

            # Handle case-insensitive filesystems (macOS, Windows)
            # Normalize to lowercase for comparison on case-insensitive systems
            case_sensitive = self._is_case_sensitive_filesystem(vault_real)

            if case_sensitive:
                # Case-sensitive filesystem - exact byte comparison
                vault_normalized = vault_real
                candidate_normalized = candidate_real
            else:
                # Case-insensitive filesystem - compare lowercased paths
                vault_normalized = vault_real.lower()
                candidate_normalized = candidate_real.lower()

            # Verify resolved path is within vault
            # Use sep to ensure we match directory boundaries, not substring
            vault_with_sep = vault_normalized + os.sep

            if not (
                candidate_normalized == vault_normalized or
                candidate_normalized.startswith(vault_with_sep)
            ):
                raise ValueError(
                    f"Path traversal detected: attempted to escape vault\n"
                    f"  Requested: {relative_path}\n"
                    f"  Resolved to: {candidate_real}\n"
                    f"  Vault root: {vault_real}"
                )

            # Additional check: ensure realpath didn't return something outside vault
            # This catches symlink-to-symlink chains and other edge cases
            if not os.path.commonpath([candidate_real, vault_real]) == vault_real:
                raise ValueError(
                    f"Path escape via symlink detected: {relative_path}\n"
                    f"  Resolved to: {candidate_real}\n"
                    f"  Vault root: {vault_real}"
                )

            return candidate_real

        except (OSError, ValueError) as e:
            # OSError can occur with broken symlinks or permission issues
            if isinstance(e, ValueError):
                raise  # Re-raise our ValueError
            raise ValueError(
                f"Cannot resolve path {relative_path}: {str(e)}"
            ) from e

    def _ensure_md_extension(self, path: str) -> str:
        """Ensure path has .md extension."""
        if not path.endswith(".md"):
            return f"{path}.md"
        return path

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as filename."""
        # Remove or replace invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name[:200]  # Limit length

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return frontmatter, body
        except yaml.YAMLError:
            return {}, content

    def _format_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Format metadata as YAML frontmatter."""
        if not metadata:
            return ""
        return f"---\n{yaml.dump(metadata, default_flow_style=False)}---\n\n"

    def _extract_links(self, content: str) -> List[str]:
        """Extract [[wikilinks]] from content."""
        pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
        return list(set(re.findall(pattern, content)))

    def _extract_tags(self, content: str) -> List[str]:
        """Extract #tags from content."""
        pattern = r'(?<!\S)#([a-zA-Z][a-zA-Z0-9_/-]*)'
        return list(set(re.findall(pattern, content)))

    # Note CRUD Operations

    def write_note(
        self,
        path: str,
        content: str,
        frontmatter: Optional[Dict[str, Any]] = None,
        folder: Optional[str] = None
    ) -> VaultNote:
        """Write a note to the vault."""
        # Build path
        if folder:
            path = os.path.join(folder, path)
        path = self._ensure_md_extension(path)

        # Ensure parent directory exists
        full_path = self._full_path(path)
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        # Prepare frontmatter
        fm = frontmatter or {}
        now = datetime.now(timezone.utc).isoformat()

        # Check if file exists for created_at
        if os.path.exists(full_path):
            existing_note = self.read_note(path)
            if existing_note:
                fm.setdefault("created", existing_note.frontmatter.get("created", now))
        else:
            fm.setdefault("created", now)

        fm["modified"] = now

        # Extract title from first heading or filename
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            fm.setdefault("title", title_match.group(1))
        else:
            fm.setdefault("title", Path(path).stem)

        # Write file
        full_content = self._format_frontmatter(fm) + content
        Path(full_path).write_text(full_content, encoding="utf-8")

        return VaultNote(
            path=path,
            title=fm.get("title", Path(path).stem),
            content=content,
            frontmatter=fm,
            links=self._extract_links(content),
            tags=fm.get("tags", []) + self._extract_tags(content),
            created_at=fm.get("created", now),
            modified_at=fm.get("modified", now)
        )

    def read_note(self, path: str) -> Optional[VaultNote]:
        """Read a note from the vault."""
        path = self._ensure_md_extension(path)
        full_path = self._full_path(path)

        if not os.path.exists(full_path):
            return None

        raw_content = Path(full_path).read_text(encoding="utf-8")
        frontmatter, content = self._parse_frontmatter(raw_content)

        stat = os.stat(full_path)

        return VaultNote(
            path=path,
            title=frontmatter.get("title", Path(path).stem),
            content=content,
            frontmatter=frontmatter,
            links=self._extract_links(content),
            tags=frontmatter.get("tags", []) + self._extract_tags(content),
            created_at=frontmatter.get("created", datetime.fromtimestamp(stat.st_ctime).isoformat()),
            modified_at=frontmatter.get("modified", datetime.fromtimestamp(stat.st_mtime).isoformat())
        )

    def delete_note(self, path: str) -> bool:
        """Delete a note from the vault."""
        path = self._ensure_md_extension(path)
        full_path = self._full_path(path)

        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def note_exists(self, path: str) -> bool:
        """Check if a note exists."""
        path = self._ensure_md_extension(path)
        return os.path.exists(self._full_path(path))

    # Specialized Note Types

    def write_code_note(
        self,
        filename: str,
        code: str,
        language: str,
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> VaultNote:
        """Write a code snippet note."""
        sanitized = self._sanitize_filename(Path(filename).stem)
        path = f"{self.FOLDER_CODE}/{sanitized}"

        content = f"# {filename}\n\n"
        if description:
            content += f"{description}\n\n"
        content += f"```{language}\n{code}\n```\n"

        frontmatter = {
            "type": "code",
            "language": language,
            "original_file": filename,
            "tags": tags or ["code", language]
        }

        return self.write_note(path, content, frontmatter)

    def write_conversation_note(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        summary: str = ""
    ) -> VaultNote:
        """Write a conversation log."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = f"{self.FOLDER_CONVERSATIONS}/{date_str}-{session_id[:8]}"

        content = f"# Conversation {session_id[:8]}\n\n"
        if summary:
            content += f"**Summary:** {summary}\n\n---\n\n"

        for msg in messages:
            role = msg.get("role", "unknown").title()
            text = msg.get("content", "")
            content += f"**{role}:**\n{text}\n\n"

        frontmatter = {
            "type": "conversation",
            "session_id": session_id,
            "date": date_str,
            "message_count": len(messages),
            "tags": ["conversation"]
        }

        return self.write_note(path, content, frontmatter)

    def write_daily_note(self, date: Optional[datetime] = None) -> VaultNote:
        """Create or get a daily note."""
        date = date or datetime.now(timezone.utc)
        date_str = date.strftime("%Y-%m-%d")
        path = f"{self.FOLDER_DAILY}/{date_str}"

        if self.note_exists(path):
            return self.read_note(path)

        content = f"# {date_str}\n\n## Tasks\n\n- [ ] \n\n## Notes\n\n"

        frontmatter = {
            "type": "daily",
            "date": date_str,
            "tags": ["daily"]
        }

        return self.write_note(path, content, frontmatter)

    def write_reference_note(
        self,
        title: str,
        content: str,
        source: str,
        tags: Optional[List[str]] = None
    ) -> VaultNote:
        """Write a reference/documentation note."""
        sanitized = self._sanitize_filename(title)
        path = f"{self.FOLDER_REFERENCES}/{sanitized}"

        full_content = f"# {title}\n\n**Source:** {source}\n\n{content}"

        frontmatter = {
            "type": "reference",
            "source": source,
            "tags": tags or ["reference"]
        }

        return self.write_note(path, full_content, frontmatter)

    # Search and Query

    def list_notes(self, folder: Optional[str] = None) -> List[str]:
        """List all note paths in vault or folder."""
        search_path = Path(self.path)
        if folder:
            search_path = search_path / folder

        notes = []
        for md_file in search_path.rglob("*.md"):
            rel_path = str(md_file.relative_to(self.path))
            notes.append(rel_path)

        return sorted(notes)

    def search_notes(self, query: str, folder: Optional[str] = None) -> List[VaultNote]:
        """Simple text search across notes."""
        results = []
        query_lower = query.lower()

        for path in self.list_notes(folder):
            note = self.read_note(path)
            if note:
                # Search in title, content, and tags
                if (query_lower in note.title.lower() or
                    query_lower in note.content.lower() or
                    any(query_lower in tag.lower() for tag in note.tags)):
                    results.append(note)

        return results

    def get_backlinks(self, note_path: str) -> List[VaultNote]:
        """Find notes that link to the given note."""
        note_path = self._ensure_md_extension(note_path)
        note_name = Path(note_path).stem

        backlinks = []
        for path in self.list_notes():
            if path == note_path:
                continue
            note = self.read_note(path)
            if note and note_name in note.links:
                backlinks.append(note)

        return backlinks

    def get_by_tag(self, tag: str, folder: Optional[str] = None) -> List[VaultNote]:
        """Get all notes with a specific tag."""
        results = []
        tag_lower = tag.lower().lstrip("#")

        for path in self.list_notes(folder):
            note = self.read_note(path)
            if note:
                note_tags = [t.lower() for t in note.tags]
                if tag_lower in note_tags:
                    results.append(note)

        return results

    def get_recent_notes(self, limit: int = 20) -> List[VaultNote]:
        """Get most recently modified notes."""
        notes = []
        for path in self.list_notes():
            note = self.read_note(path)
            if note:
                notes.append(note)

        # Sort by modified_at descending
        notes.sort(key=lambda n: n.modified_at, reverse=True)
        return notes[:limit]

    # Utility

    def get_stats(self) -> Dict[str, Any]:
        """Get vault statistics."""
        all_notes = self.list_notes()
        all_tags = set()
        total_links = 0

        for path in all_notes:
            note = self.read_note(path)
            if note:
                all_tags.update(note.tags)
                total_links += len(note.links)

        # Count by folder
        by_folder = {}
        for path in all_notes:
            folder = path.split("/")[0] if "/" in path else "root"
            by_folder[folder] = by_folder.get(folder, 0) + 1

        return {
            "total_notes": len(all_notes),
            "by_folder": by_folder,
            "unique_tags": len(all_tags),
            "total_links": total_links,
            "vault_path": self.path
        }

    def export_graph_data(self) -> Dict[str, Any]:
        """Export data for graph visualization (like Obsidian's graph view)."""
        nodes = []
        edges = []

        for path in self.list_notes():
            note = self.read_note(path)
            if note:
                node_id = Path(path).stem
                nodes.append({
                    "id": node_id,
                    "path": path,
                    "title": note.title,
                    "tags": note.tags
                })

                for link in note.links:
                    edges.append({
                        "source": node_id,
                        "target": link
                    })

        return {"nodes": nodes, "edges": edges}
