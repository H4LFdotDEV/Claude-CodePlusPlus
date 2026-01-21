# test_vault_manager.py
# Tests for Obsidian-compatible vault manager

import pytest
from pathlib import Path
from memory_mcp.vault_manager import VaultManager, VaultNote


class TestVaultManager:
    """Tests for VaultManager class."""

    def test_vault_creation(self, vault_manager):
        """Test vault directory structure is created."""
        assert vault_manager is not None
        vault_path = Path(vault_manager.path)
        assert vault_path.exists()
        assert (vault_path / "code").exists()
        assert (vault_path / "notes").exists()
        assert (vault_path / "conversations").exists()

    def test_write_note(self, vault_manager):
        """Test writing a simple note."""
        note = vault_manager.write_note(
            path="test-note",
            content="# Test Note\n\nThis is a test.",
        )
        assert note is not None
        assert note.title == "Test Note"
        assert "test" in note.path.lower()

    def test_write_note_with_frontmatter(self, vault_manager):
        """Test writing a note with frontmatter."""
        note = vault_manager.write_note(
            path="frontmatter-test",
            content="# Test\n\nContent",
            frontmatter={"custom": "value", "tags": ["test"]},
        )
        assert note.frontmatter["custom"] == "value"

    def test_write_note_to_folder(self, vault_manager):
        """Test writing a note to a specific folder."""
        note = vault_manager.write_note(
            path="my-note",
            content="Content",
            folder="notes",
        )
        assert "notes/" in note.path

    def test_read_note(self, vault_manager):
        """Test reading a note."""
        vault_manager.write_note(
            path="read-test",
            content="# Read Test\n\nContent to read.",
        )
        note = vault_manager.read_note("read-test")
        assert note is not None
        assert "Content to read" in note.content

    def test_read_nonexistent_note(self, vault_manager):
        """Test reading nonexistent note returns None."""
        note = vault_manager.read_note("nonexistent")
        assert note is None

    def test_delete_note(self, vault_manager):
        """Test deleting a note."""
        vault_manager.write_note(path="to-delete", content="Delete me")
        assert vault_manager.note_exists("to-delete")

        result = vault_manager.delete_note("to-delete")
        assert result is True
        assert not vault_manager.note_exists("to-delete")

    def test_delete_nonexistent_note(self, vault_manager):
        """Test deleting nonexistent note returns False."""
        result = vault_manager.delete_note("nonexistent")
        assert result is False

    def test_note_exists(self, vault_manager):
        """Test checking if note exists."""
        assert not vault_manager.note_exists("check-exists")
        vault_manager.write_note(path="check-exists", content="Exists")
        assert vault_manager.note_exists("check-exists")

    def test_write_code_note(self, vault_manager):
        """Test writing a code snippet note."""
        code = "def hello():\n    print('Hello')"
        note = vault_manager.write_code_note(
            filename="hello.py",
            code=code,
            language="python",
            description="A greeting function",
            tags=["utility"],
        )
        assert note is not None
        assert "```python" in note.content
        assert code in note.content
        assert note.frontmatter["language"] == "python"

    def test_write_conversation_note(self, vault_manager):
        """Test writing a conversation log."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        note = vault_manager.write_conversation_note(
            session_id="test-session-123",
            messages=messages,
            summary="A greeting exchange",
        )
        assert note is not None
        assert "User" in note.content
        assert "Assistant" in note.content
        assert note.frontmatter["type"] == "conversation"

    def test_write_daily_note(self, vault_manager):
        """Test creating a daily note."""
        note = vault_manager.write_daily_note()
        assert note is not None
        assert note.frontmatter["type"] == "daily"
        assert "## Tasks" in note.content

    def test_write_reference_note(self, vault_manager):
        """Test writing a reference note."""
        note = vault_manager.write_reference_note(
            title="API Reference",
            content="Documentation content here.",
            source="https://docs.example.com",
            tags=["api", "docs"],
        )
        assert note is not None
        assert note.frontmatter["type"] == "reference"
        assert "Source:" in note.content

    def test_list_notes(self, vault_manager):
        """Test listing all notes."""
        vault_manager.write_note(path="list-test-1", content="One")
        vault_manager.write_note(path="list-test-2", content="Two")

        notes = vault_manager.list_notes()
        assert len(notes) >= 2

    def test_list_notes_in_folder(self, vault_manager):
        """Test listing notes in specific folder."""
        vault_manager.write_note(path="folder-test", content="In notes", folder="notes")

        notes = vault_manager.list_notes(folder="notes")
        assert any("folder-test" in n for n in notes)

    def test_search_notes(self, vault_manager):
        """Test searching notes."""
        vault_manager.write_note(path="search-1", content="Python programming guide")
        vault_manager.write_note(path="search-2", content="JavaScript tutorial")

        results = vault_manager.search_notes("python")
        assert len(results) >= 1
        assert any("python" in r.content.lower() for r in results)

    def test_search_notes_by_tag(self, vault_manager):
        """Test searching notes in tags."""
        vault_manager.write_note(
            path="tag-search",
            content="Content with #searchable tag",
        )

        results = vault_manager.search_notes("searchable")
        assert len(results) >= 1

    def test_get_by_tag(self, vault_manager):
        """Test getting notes by tag."""
        vault_manager.write_note(
            path="tagged-note",
            content="Has tag #important here",
        )

        results = vault_manager.get_by_tag("important")
        assert len(results) >= 1

    def test_get_recent_notes(self, vault_manager):
        """Test getting recent notes."""
        for i in range(5):
            vault_manager.write_note(path=f"recent-{i}", content=f"Note {i}")

        results = vault_manager.get_recent_notes(limit=3)
        assert len(results) == 3

    def test_extract_wikilinks(self, vault_manager):
        """Test extracting [[wikilinks]] from content."""
        vault_manager.write_note(
            path="with-links",
            content="Links to [[other-note]] and [[another|alias]]",
        )

        note = vault_manager.read_note("with-links")
        assert "other-note" in note.links
        assert "another" in note.links

    def test_extract_tags_from_content(self, vault_manager):
        """Test extracting #tags from content."""
        vault_manager.write_note(
            path="with-tags",
            content="Has #tag1 and #tag2 in content",
        )

        note = vault_manager.read_note("with-tags")
        assert "tag1" in note.tags
        assert "tag2" in note.tags

    def test_get_backlinks(self, vault_manager):
        """Test getting backlinks to a note."""
        vault_manager.write_note(path="target-note", content="Target")
        vault_manager.write_note(
            path="linking-note",
            content="Links to [[target-note]]",
        )

        backlinks = vault_manager.get_backlinks("target-note")
        assert len(backlinks) >= 1

    def test_get_stats(self, vault_manager):
        """Test getting vault statistics."""
        vault_manager.write_note(path="stats-1", content="One #tagged")
        vault_manager.write_note(path="stats-2", content="Two [[linked]]")

        stats = vault_manager.get_stats()
        assert stats["total_notes"] >= 2
        assert stats["vault_path"] == vault_manager.path

    def test_export_graph_data(self, vault_manager):
        """Test exporting graph visualization data."""
        vault_manager.write_note(path="node-1", content="First [[node-2]]")
        vault_manager.write_note(path="node-2", content="Second")

        graph = vault_manager.export_graph_data()
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) >= 2

    def test_sanitize_filename(self, vault_manager):
        """Test filename sanitization."""
        # Should handle special characters
        note = vault_manager.write_note(
            path="file:with/special*chars?",
            content="Content",
        )
        assert note is not None
        # File should have been created with sanitized name

    def test_md_extension_handling(self, vault_manager):
        """Test that .md extension is handled correctly."""
        vault_manager.write_note(path="with-ext.md", content="Has extension")
        vault_manager.write_note(path="without-ext", content="No extension")

        assert vault_manager.note_exists("with-ext")
        assert vault_manager.note_exists("without-ext")
        assert vault_manager.note_exists("with-ext.md")
        assert vault_manager.note_exists("without-ext.md")

    def test_path_traversal_protection(self, vault_manager):
        """Test that path traversal attacks are blocked."""
        # These should all raise ValueError
        with pytest.raises(ValueError, match="Path traversal detected"):
            vault_manager.read_note("../../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal detected"):
            vault_manager.write_note("../../../tmp/malicious", "content")

        with pytest.raises(ValueError, match="Path traversal detected"):
            vault_manager.delete_note("..\\..\\Windows\\System32\\config")
