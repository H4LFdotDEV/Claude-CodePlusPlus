# faiss_manager.py
# FAISS Vector Index Manager for Claude Code++
# Jeremiah Kroesche | Halfservers LLC
#
# Warm memory layer - semantic similarity search

import json
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

from .config import get_config, FAISSConfig


@dataclass
class SearchResult:
    doc_id: str
    distance: float
    score: float  # Normalized similarity score (0-1)


class FAISSManager:
    """Manages FAISS index for semantic similarity search."""

    def __init__(self, config: Optional[FAISSConfig] = None, path: Optional[str] = None):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed. Run: pip install faiss-cpu")

        self.config = config or get_config().faiss
        self.path = path or get_config().faiss_path
        self.path = os.path.expanduser(self.path)

        self.dimension = self.config.dimension
        self.index: Optional[faiss.Index] = None
        self.id_map: Dict[int, str] = {}  # FAISS ID -> document ID
        self.reverse_map: Dict[str, int] = {}  # document ID -> FAISS ID
        self.deleted: set = set()  # Deleted FAISS IDs (for lazy deletion)
        self.total_added: int = 0  # Total documents ever added
        self.deleted_count: int = 0  # Count of deleted documents

        self._load_or_create()

    def _create_index(self) -> faiss.Index:
        """Create a new FAISS index based on config."""
        index_type = self.config.index_type.lower()

        if index_type == "flat":
            # Exact search - best for small datasets
            return faiss.IndexFlatL2(self.dimension)

        elif index_type == "ivf":
            # Approximate search with clustering
            quantizer = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(quantizer, self.dimension, self.config.nlist)
            return index

        elif index_type == "hnsw":
            # Graph-based approximate search
            index = faiss.IndexHNSWFlat(self.dimension, 32)  # M=32
            return index

        else:
            # Default to flat
            return faiss.IndexFlatL2(self.dimension)

    def _load_or_create(self):
        """Load existing index or create new one."""
        index_path = os.path.join(self.path, "index.faiss")
        map_path = os.path.join(self.path, "id_map.json")
        deleted_path = os.path.join(self.path, "deleted.json")

        if os.path.exists(index_path) and os.path.exists(map_path):
            self.index = faiss.read_index(index_path)
            with open(map_path) as f:
                data = json.load(f)
                # JSON keys are strings, convert to int
                self.id_map = {int(k): v for k, v in data.items()}
                self.reverse_map = {v: int(k) for k, v in data.items()}

            if os.path.exists(deleted_path):
                with open(deleted_path) as f:
                    deleted_data = json.load(f)
                    # Support both legacy format (list) and new format (dict)
                    if isinstance(deleted_data, dict):
                        self.deleted = set(deleted_data.get("ids", []))
                        self.total_added = deleted_data.get("total_added", len(self.id_map))
                        self.deleted_count = deleted_data.get("deleted_count", len(self.deleted))
                    else:
                        self.deleted = set(deleted_data)
                        self.total_added = len(self.id_map)
                        self.deleted_count = len(self.deleted)
            else:
                self.total_added = len(self.id_map)
                self.deleted_count = 0
        else:
            self.index = self._create_index()
            self.id_map = {}
            self.reverse_map = {}
            self.deleted = set()
            self.total_added = 0
            self.deleted_count = 0

    def save(self):
        """Save index and mappings to disk."""
        Path(self.path).mkdir(parents=True, exist_ok=True)

        index_path = os.path.join(self.path, "index.faiss")
        map_path = os.path.join(self.path, "id_map.json")
        deleted_path = os.path.join(self.path, "deleted.json")

        faiss.write_index(self.index, index_path)
        with open(map_path, "w") as f:
            json.dump(self.id_map, f)
        with open(deleted_path, "w") as f:
            # Save deletion tracking data with metadata
            json.dump({
                "ids": list(self.deleted),
                "total_added": self.total_added,
                "deleted_count": self.deleted_count
            }, f)

    def add(self, doc_id: str, embedding: np.ndarray) -> int:
        """Add a document embedding to the index."""
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)

        # Ensure float32
        embedding = embedding.astype(np.float32)

        # Check if document already exists
        if doc_id in self.reverse_map:
            # Mark old entry as deleted and add new one
            old_faiss_id = self.reverse_map[doc_id]
            self.deleted.add(old_faiss_id)

        # Get next FAISS ID
        faiss_id = self.index.ntotal

        # Add to index
        self.index.add(embedding)

        # Update mappings
        self.id_map[faiss_id] = doc_id
        self.reverse_map[doc_id] = faiss_id

        # Track total additions
        self.total_added += 1

        return faiss_id

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[SearchResult]:
        """Search for similar documents."""
        if self.index.ntotal == 0:
            return []

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        query_embedding = query_embedding.astype(np.float32)

        # Search for more than k to account for deleted entries
        search_k = min(k * 2 + len(self.deleted), self.index.ntotal)
        distances, indices = self.index.search(query_embedding, search_k)

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue
            if idx in self.deleted:
                continue
            if idx not in self.id_map:
                continue

            doc_id = self.id_map[idx]

            # Convert L2 distance to similarity score (0-1)
            # Lower distance = higher similarity
            score = 1 / (1 + dist)

            results.append(SearchResult(
                doc_id=doc_id,
                distance=float(dist),
                score=float(score)
            ))

            if len(results) >= k:
                break

        return results

    def delete(self, doc_id: str) -> bool:
        """Mark a document as deleted (lazy deletion)."""
        if doc_id not in self.reverse_map:
            return False

        faiss_id = self.reverse_map[doc_id]
        self.deleted.add(faiss_id)
        self.deleted_count += 1

        # Check if index needs compaction after deletion
        self.maybe_rebuild()

        return True

    def get_embedding(self, doc_id: str) -> Optional[np.ndarray]:
        """Retrieve the embedding for a document."""
        if doc_id not in self.reverse_map:
            return None

        faiss_id = self.reverse_map[doc_id]
        if faiss_id in self.deleted:
            return None

        # Reconstruct embedding from index
        embedding = np.zeros((1, self.dimension), dtype=np.float32)
        self.index.reconstruct(faiss_id, embedding[0])
        return embedding[0]

    def needs_rebuild(self) -> bool:
        """Check if index needs compaction."""
        if self.total_added == 0:
            return False
        deletion_ratio = self.deleted_count / self.total_added
        return deletion_ratio > 0.3  # 30% threshold

    def maybe_rebuild(self) -> None:
        """Rebuild index if needed, with progress logging."""
        if self.needs_rebuild():
            print(f"Rebuilding FAISS index: {self.deleted_count}/{self.total_added} deleted")

    def rebuild(self, embeddings_loader):
        """
        Rebuild index from scratch.

        Args:
            embeddings_loader: Callable that returns iterator of (doc_id, embedding) tuples
        """
        # Create new index
        new_index = self._create_index()
        new_id_map = {}
        new_reverse_map = {}

        # Add all non-deleted embeddings
        for doc_id, embedding in embeddings_loader():
            if doc_id in self.reverse_map and self.reverse_map[doc_id] in self.deleted:
                continue  # Skip deleted documents

            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            embedding = embedding.astype(np.float32)

            faiss_id = new_index.ntotal
            new_index.add(embedding)
            new_id_map[faiss_id] = doc_id
            new_reverse_map[doc_id] = faiss_id

        # Swap indices
        self.index = new_index
        self.id_map = new_id_map
        self.reverse_map = new_reverse_map
        self.deleted = set()

        # Reset tracking counters after rebuild
        self.total_added = len(new_id_map)
        self.deleted_count = 0

        self.save()

    @property
    def count(self) -> int:
        """Number of active (non-deleted) documents."""
        return self.index.ntotal - len(self.deleted)

    def __len__(self) -> int:
        return self.count
