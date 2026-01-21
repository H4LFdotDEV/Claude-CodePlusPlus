# test_sqlite_index.py
# Tests for SQLite metadata index

import pytest
from memory_mcp.sqlite_index import SQLiteIndex, MemoryDocument


class TestMemoryDocument:
    """Tests for MemoryDocument dataclass."""

    def test_document_creation(self):
        """Test creating a document with defaults."""
        doc = MemoryDocument(
            id="test-001",
            content="Test content",
            doc_type="note",
            source="test.py",
        )
        assert doc.id == "test-001"
        assert doc.content == "Test content"
        assert doc.tags == []
        assert doc.metadata == {}
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_with_all_fields(self, sample_document):
        """Test document with all fields populated."""
        assert sample_document.project == "test-project"
        assert "test" in sample_document.tags
        assert sample_document.metadata["key"] == "value"

    def test_document_to_dict(self, sample_document):
        """Test converting document to dictionary."""
        d = sample_document.to_dict()
        assert isinstance(d["tags"], str)  # JSON serialized
        assert isinstance(d["metadata"], str)  # JSON serialized


class TestSQLiteIndex:
    """Tests for SQLiteIndex class."""

    def test_index_creation(self, sqlite_index):
        """Test SQLite index is created properly."""
        assert sqlite_index is not None
        assert sqlite_index.count() == 0

    def test_insert_document(self, sqlite_index, sample_document):
        """Test inserting a document."""
        result = sqlite_index.insert(sample_document)
        assert result is True
        assert sqlite_index.count() == 1

    def test_insert_duplicate_fails(self, sqlite_index, sample_document):
        """Test inserting duplicate document fails."""
        sqlite_index.insert(sample_document)
        result = sqlite_index.insert(sample_document)
        assert result is False

    def test_get_document(self, sqlite_index, sample_document):
        """Test retrieving a document by ID."""
        sqlite_index.insert(sample_document)
        retrieved = sqlite_index.get(sample_document.id)
        assert retrieved is not None
        assert retrieved.id == sample_document.id
        assert retrieved.content == sample_document.content

    def test_get_nonexistent_returns_none(self, sqlite_index):
        """Test getting nonexistent document returns None."""
        result = sqlite_index.get("nonexistent-id")
        assert result is None

    def test_update_document(self, sqlite_index, sample_document):
        """Test updating a document."""
        sqlite_index.insert(sample_document)
        sample_document.content = "Updated content"
        result = sqlite_index.update(sample_document)
        assert result is True

        retrieved = sqlite_index.get(sample_document.id)
        assert retrieved.content == "Updated content"

    def test_upsert_insert(self, sqlite_index, sample_document):
        """Test upsert inserts new document."""
        result = sqlite_index.upsert(sample_document)
        assert result is True
        assert sqlite_index.count() == 1

    def test_upsert_update(self, sqlite_index, sample_document):
        """Test upsert updates existing document."""
        sqlite_index.insert(sample_document)
        sample_document.content = "Upserted content"
        result = sqlite_index.upsert(sample_document)
        assert result is True

        retrieved = sqlite_index.get(sample_document.id)
        assert retrieved.content == "Upserted content"

    def test_delete_document(self, sqlite_index, sample_document):
        """Test deleting a document."""
        sqlite_index.insert(sample_document)
        result = sqlite_index.delete(sample_document.id)
        assert result is True
        assert sqlite_index.count() == 0

    def test_delete_nonexistent_returns_false(self, sqlite_index):
        """Test deleting nonexistent document returns False."""
        result = sqlite_index.delete("nonexistent-id")
        assert result is False

    def test_search_fulltext(self, sqlite_index, sample_documents):
        """Test full-text search."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.search_fulltext("python")
        assert len(results) >= 1
        assert any("python" in r.content.lower() for r in results)

    def test_search_by_type(self, sqlite_index, sample_documents):
        """Test search by document type."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.search_by_type("code")
        assert len(results) == 2  # python and javascript
        assert all(r.doc_type == "code" for r in results)

    def test_search_by_project(self, sqlite_index, sample_documents):
        """Test search by project."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.search_by_project("test-project")
        assert len(results) == len(sample_documents)

    def test_search_by_tag(self, sqlite_index, sample_documents):
        """Test search by tag."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.search_by_tag("python")
        assert len(results) >= 1

    def test_search_by_source(self, sqlite_index, sample_documents):
        """Test search by source pattern."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.search_by_source("file1")
        assert len(results) >= 1

    def test_get_recent(self, sqlite_index, sample_documents):
        """Test getting recent documents."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        results = sqlite_index.get_recent(limit=3)
        assert len(results) == 3

    def test_count_by_type(self, sqlite_index, sample_documents):
        """Test counting documents by type."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        total = sqlite_index.count()
        code_count = sqlite_index.count("code")
        assert total == len(sample_documents)
        assert code_count == 2

    def test_get_all_tags(self, sqlite_index, sample_documents):
        """Test getting all unique tags."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        tags = sqlite_index.get_all_tags()
        assert "test" in tags
        assert "python" in tags

    def test_get_all_projects(self, sqlite_index, sample_documents):
        """Test getting all unique projects."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        projects = sqlite_index.get_all_projects()
        assert "test-project" in projects

    def test_get_stats(self, sqlite_index, sample_documents):
        """Test getting database statistics."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        stats = sqlite_index.get_stats()
        assert stats["total_documents"] == len(sample_documents)
        assert "code" in stats["by_type"]
        assert stats["database_size_bytes"] > 0

    def test_iter_all(self, sqlite_index, sample_documents):
        """Test iterating over all documents."""
        for doc in sample_documents:
            sqlite_index.insert(doc)

        all_docs = list(sqlite_index.iter_all(batch_size=2))
        assert len(all_docs) == len(sample_documents)

    def test_get_by_embedding_ids(self, sqlite_index, sample_document):
        """Test getting documents by embedding IDs."""
        sample_document.embedding_id = "embed-001"
        sqlite_index.insert(sample_document)

        results = sqlite_index.get_by_embedding_ids(["embed-001"])
        assert len(results) == 1
        assert results[0].id == sample_document.id

    def test_get_by_embedding_ids_empty(self, sqlite_index):
        """Test getting documents with empty embedding IDs list."""
        results = sqlite_index.get_by_embedding_ids([])
        assert results == []
