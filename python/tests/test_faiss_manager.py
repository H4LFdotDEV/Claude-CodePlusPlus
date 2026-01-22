# test_faiss_manager.py
# Tests for FAISS vector index manager

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Check if FAISS is available
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


pytestmark = pytest.mark.skipif(not FAISS_AVAILABLE, reason="FAISS not installed")


class TestFAISSManager:
    """Tests for FAISSManager class."""

    @pytest.fixture
    def faiss_manager(self, test_config):
        """Create a FAISS manager for testing."""
        from memory_mcp.faiss_manager import FAISSManager
        return FAISSManager(config=test_config.faiss, path=test_config.faiss_path)

    @pytest.fixture
    def random_embedding(self):
        """Generate a random embedding vector."""
        return np.random.rand(768).astype(np.float32)

    def test_manager_creation(self, faiss_manager):
        """Test FAISS manager is created properly."""
        assert faiss_manager is not None
        assert faiss_manager.count == 0
        assert faiss_manager.dimension == 768

    def test_add_embedding(self, faiss_manager, random_embedding):
        """Test adding an embedding."""
        faiss_id = faiss_manager.add("doc-001", random_embedding)
        assert faiss_id == 0
        assert faiss_manager.count == 1

    def test_add_multiple_embeddings(self, faiss_manager):
        """Test adding multiple embeddings."""
        for i in range(5):
            embedding = np.random.rand(768).astype(np.float32)
            faiss_manager.add(f"doc-{i:03d}", embedding)

        assert faiss_manager.count == 5

    def test_add_replaces_existing(self, faiss_manager, random_embedding):
        """Test adding duplicate doc_id replaces existing."""
        faiss_manager.add("doc-001", random_embedding)
        new_embedding = np.random.rand(768).astype(np.float32)
        faiss_manager.add("doc-001", new_embedding)

        # Should have 2 in index, but 1 active (old one marked deleted)
        assert faiss_manager.count == 1

    def test_search_empty_index(self, faiss_manager, random_embedding):
        """Test searching empty index returns empty list."""
        results = faiss_manager.search(random_embedding, k=5)
        assert results == []

    def test_search_returns_results(self, faiss_manager):
        """Test search returns results."""
        # Add some embeddings
        embeddings = []
        for i in range(10):
            embedding = np.random.rand(768).astype(np.float32)
            embeddings.append(embedding)
            faiss_manager.add(f"doc-{i:03d}", embedding)

        # Search with first embedding
        results = faiss_manager.search(embeddings[0], k=3)
        assert len(results) == 3
        assert results[0].doc_id == "doc-000"  # Should find itself first
        assert results[0].score > 0

    def test_search_result_structure(self, faiss_manager, random_embedding):
        """Test search result structure."""
        faiss_manager.add("doc-001", random_embedding)

        results = faiss_manager.search(random_embedding, k=1)
        assert len(results) == 1

        result = results[0]
        assert hasattr(result, "doc_id")
        assert hasattr(result, "distance")
        assert hasattr(result, "score")
        assert 0 <= result.score <= 1

    def test_delete_embedding(self, faiss_manager, random_embedding):
        """Test deleting an embedding (lazy deletion)."""
        faiss_manager.add("doc-001", random_embedding)
        assert faiss_manager.count == 1

        result = faiss_manager.delete("doc-001")
        assert result is True
        assert faiss_manager.count == 0

    def test_delete_nonexistent(self, faiss_manager):
        """Test deleting nonexistent returns False."""
        result = faiss_manager.delete("nonexistent")
        assert result is False

    def test_deleted_not_in_search(self, faiss_manager):
        """Test deleted documents don't appear in search."""
        embeddings = []
        for i in range(5):
            embedding = np.random.rand(768).astype(np.float32)
            embeddings.append(embedding)
            faiss_manager.add(f"doc-{i:03d}", embedding)

        # Delete middle document
        faiss_manager.delete("doc-002")

        # Search with doc-002's embedding
        results = faiss_manager.search(embeddings[2], k=10)
        doc_ids = [r.doc_id for r in results]
        assert "doc-002" not in doc_ids

    def test_get_embedding(self, faiss_manager, random_embedding):
        """Test retrieving stored embedding."""
        faiss_manager.add("doc-001", random_embedding)

        retrieved = faiss_manager.get_embedding("doc-001")
        assert retrieved is not None
        assert retrieved.shape == (768,)
        # Check approximate equality (may have small floating point differences)
        np.testing.assert_array_almost_equal(retrieved, random_embedding, decimal=5)

    def test_get_embedding_nonexistent(self, faiss_manager):
        """Test getting nonexistent embedding returns None."""
        result = faiss_manager.get_embedding("nonexistent")
        assert result is None

    def test_get_embedding_deleted(self, faiss_manager, random_embedding):
        """Test getting deleted embedding returns None."""
        faiss_manager.add("doc-001", random_embedding)
        faiss_manager.delete("doc-001")

        result = faiss_manager.get_embedding("doc-001")
        assert result is None

    def test_save_and_load(self, faiss_manager, random_embedding, test_config):
        """Test saving and loading index."""
        from memory_mcp.faiss_manager import FAISSManager

        faiss_manager.add("doc-001", random_embedding)
        faiss_manager.save()

        # Create new manager that should load the saved index
        new_manager = FAISSManager(
            config=test_config.faiss,
            path=test_config.faiss_path
        )
        assert new_manager.count == 1
        assert "doc-001" in new_manager.reverse_map

    def test_needs_rebuild(self, faiss_manager):
        """Test rebuild threshold detection and automatic rebuild."""
        # Initially shouldn't need rebuild
        assert not faiss_manager.needs_rebuild()

        # Add 10 documents
        for i in range(10):
            embedding = np.random.rand(768).astype(np.float32)
            faiss_manager.add(f"doc-{i:03d}", embedding)

        # Delete 2 (20% > 10% threshold) - this triggers automatic rebuild via maybe_rebuild()
        faiss_manager.delete("doc-000")
        faiss_manager.delete("doc-001")

        # After automatic rebuild, needs_rebuild should return False
        # (the delete method calls maybe_rebuild() which rebuilds when threshold exceeded)
        assert not faiss_manager.needs_rebuild()

    def test_len(self, faiss_manager, random_embedding):
        """Test __len__ returns count."""
        assert len(faiss_manager) == 0
        faiss_manager.add("doc-001", random_embedding)
        assert len(faiss_manager) == 1

    def test_1d_embedding_reshaped(self, faiss_manager):
        """Test 1D embedding is properly reshaped."""
        embedding = np.random.rand(768).astype(np.float32)
        faiss_id = faiss_manager.add("doc-001", embedding)
        assert faiss_id >= 0

    def test_search_limits_results(self, faiss_manager):
        """Test search respects k limit."""
        for i in range(20):
            embedding = np.random.rand(768).astype(np.float32)
            faiss_manager.add(f"doc-{i:03d}", embedding)

        query = np.random.rand(768).astype(np.float32)
        results = faiss_manager.search(query, k=5)
        assert len(results) == 5


class TestFAISSManagerUnavailable:
    """Tests for when FAISS is not available."""

    def test_import_error_without_faiss(self, test_config, monkeypatch):
        """Test ImportError raised when FAISS not available."""
        # This test verifies the error handling when faiss is not installed
        # We can't really test this without uninstalling faiss
        pass
