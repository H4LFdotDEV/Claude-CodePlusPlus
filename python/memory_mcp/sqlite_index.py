# sqlite_index.py
# SQLite Metadata Index for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Cold storage layer - persistent metadata, full-text search

import os
import re
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from contextlib import contextmanager

from .config import get_config, SQLiteConfig


@dataclass
class MemoryDocument:
    """A document stored in the memory system."""
    id: str
    content: str
    doc_type: str  # code, note, conversation, reference
    source: str  # file path, URL, or identifier
    project: Optional[str] = None
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    embedding_id: Optional[str] = None  # Reference to FAISS
    vault_path: Optional[str] = None  # Reference to markdown file
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tags"] = json.dumps(self.tags)
        d["metadata"] = json.dumps(self.metadata)
        return d

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MemoryDocument":
        return cls(
            id=row["id"],
            content=row["content"],
            doc_type=row["doc_type"],
            source=row["source"],
            project=row["project"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding_id=row["embedding_id"],
            vault_path=row["vault_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


class SQLiteIndex:
    """SQLite-based metadata index with full-text search."""

    SCHEMA_VERSION = 1

    def __init__(self, config: Optional[SQLiteConfig] = None, path: Optional[str] = None):
        self.config = config or get_config().sqlite
        self.path = path or self.config.path
        self.path = os.path.expanduser(self.path)

        # Ensure directory exists
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory and performance optimizations."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # Performance optimizations
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrency
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance durability and performance
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    project TEXT,
                    tags TEXT,
                    metadata TEXT,
                    embedding_id TEXT,
                    vault_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Full-text search index
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    id,
                    content,
                    source,
                    tags,
                    content='documents',
                    content_rowid='rowid'
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, id, content, source, tags)
                    VALUES (new.rowid, new.id, new.content, new.source, new.tags);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, id, content, source, tags)
                    VALUES('delete', old.rowid, old.id, old.content, old.source, old.tags);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, id, content, source, tags)
                    VALUES('delete', old.rowid, old.id, old.content, old.source, old.tags);
                    INSERT INTO documents_fts(rowid, id, content, source, tags)
                    VALUES (new.rowid, new.id, new.content, new.source, new.tags);
                END
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents(embedding_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at)
            """)

            # Schema version tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
            """)

            cursor.execute("INSERT OR IGNORE INTO schema_version VALUES (?)", (self.SCHEMA_VERSION,))
            conn.commit()

    # Document CRUD Operations

    def insert(self, doc: MemoryDocument) -> bool:
        """Insert a new document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO documents
                    (id, content, doc_type, source, project, tags, metadata,
                     embedding_id, vault_path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc.id, doc.content, doc.doc_type, doc.source, doc.project,
                    json.dumps(doc.tags), json.dumps(doc.metadata),
                    doc.embedding_id, doc.vault_path, doc.created_at, doc.updated_at
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update(self, doc: MemoryDocument) -> bool:
        """Update an existing document."""
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE documents SET
                    content = ?, doc_type = ?, source = ?, project = ?,
                    tags = ?, metadata = ?, embedding_id = ?, vault_path = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                doc.content, doc.doc_type, doc.source, doc.project,
                json.dumps(doc.tags), json.dumps(doc.metadata),
                doc.embedding_id, doc.vault_path, doc.updated_at, doc.id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def upsert(self, doc: MemoryDocument) -> bool:
        """Insert or update a document."""
        if self.get(doc.id):
            return self.update(doc)
        return self.insert(doc)

    def get(self, doc_id: str) -> Optional[MemoryDocument]:
        """Get a document by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if row:
                return MemoryDocument.from_row(row)
            return None

    def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
            return cursor.rowcount > 0

    # Query Operations

    # FTS5 special characters that need escaping
    _FTS5_SPECIAL_PATTERN = re.compile(r'(["\*\(\)])')
    _FTS5_OPERATORS = frozenset(['OR', 'AND', 'NOT', 'NEAR'])

    def _escape_fts_query(self, query: str) -> str:
        """
        Escape FTS5 special characters to prevent query injection.

        FTS5 special syntax includes:
        - " (phrase queries)
        - * (prefix queries)
        - OR, AND, NOT, NEAR (operators)
        - ( ) (grouping)

        We escape these by quoting the entire query as a phrase.
        """
        if not query or not query.strip():
            return '""'

        # Check if query contains any FTS5 special syntax
        has_special = bool(self._FTS5_SPECIAL_PATTERN.search(query))
        has_operators = any(
            f' {op} ' in f' {query.upper()} '
            for op in self._FTS5_OPERATORS
        )

        if has_special or has_operators:
            # Escape double quotes by doubling them, then wrap in quotes
            escaped = query.replace('"', '""')
            return f'"{escaped}"'

        return query

    def search_fulltext(self, query: str, limit: int = 20) -> List[MemoryDocument]:
        """Full-text search across documents."""
        # Escape FTS5 special characters to prevent injection
        safe_query = self._escape_fts_query(query)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.* FROM documents d
                JOIN documents_fts fts ON d.id = fts.id
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def search_by_type(self, doc_type: str, limit: int = 100) -> List[MemoryDocument]:
        """Get documents by type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM documents
                WHERE doc_type = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (doc_type, limit))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def search_by_project(self, project: str, limit: int = 100) -> List[MemoryDocument]:
        """Get documents by project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM documents
                WHERE project = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (project, limit))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def search_by_tag(self, tag: str, limit: int = 100) -> List[MemoryDocument]:
        """Get documents containing a specific tag."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # JSON array contains check
            cursor.execute("""
                SELECT * FROM documents
                WHERE tags LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f'%"{tag}"%', limit))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def search_by_source(self, source_pattern: str, limit: int = 100) -> List[MemoryDocument]:
        """Get documents matching source pattern."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM documents
                WHERE source LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{source_pattern}%", limit))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def get_recent(self, limit: int = 20) -> List[MemoryDocument]:
        """Get most recently updated documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM documents
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    def get_by_embedding_ids(self, embedding_ids: List[str]) -> List[MemoryDocument]:
        """Get documents by their embedding IDs (for FAISS result lookup)."""
        if not embedding_ids:
            return []
        placeholders = ",".join("?" * len(embedding_ids))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM documents
                WHERE embedding_id IN ({placeholders})
            """, embedding_ids)
            return [MemoryDocument.from_row(row) for row in cursor.fetchall()]

    # Utility Operations

    def count(self, doc_type: Optional[str] = None) -> int:
        """Count documents, optionally by type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if doc_type:
                cursor.execute("SELECT COUNT(*) FROM documents WHERE doc_type = ?", (doc_type,))
            else:
                cursor.execute("SELECT COUNT(*) FROM documents")
            return cursor.fetchone()[0]

    def get_all_tags(self) -> List[str]:
        """Get all unique tags."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT tags FROM documents WHERE tags IS NOT NULL")
            tags = set()
            for row in cursor.fetchall():
                if row[0]:
                    tags.update(json.loads(row[0]))
            return sorted(tags)

    def get_all_projects(self) -> List[str]:
        """Get all unique project names."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT project FROM documents WHERE project IS NOT NULL")
            return [row[0] for row in cursor.fetchall()]

    def vacuum(self):
        """Optimize database storage."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM documents")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT doc_type, COUNT(*) as count
                FROM documents
                GROUP BY doc_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Database file size
            db_size = os.path.getsize(self.path) if os.path.exists(self.path) else 0

            return {
                "total_documents": total,
                "by_type": by_type,
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2)
            }

    def iter_all(self, batch_size: int = 100):
        """Iterate over all documents in batches."""
        offset = 0
        while True:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM documents
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))
                rows = cursor.fetchall()
                if not rows:
                    break
                for row in rows:
                    yield MemoryDocument.from_row(row)
                offset += batch_size
