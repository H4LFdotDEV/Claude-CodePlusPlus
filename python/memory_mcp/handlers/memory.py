# handlers/memory.py
# Memory operations handler (store, search, recall, delete, list)

import uuid
import logging
from typing import Dict, Any

from .base import BaseHandler
from ..sqlite_index import MemoryDocument
from ..validation import (
    validate_string, validate_list, validate_doc_type,
    validate_tags, validate_project, validate_content, validate_limit
)
from shared.log_utils import log_safe_query

logger = logging.getLogger("memory_mcp")


class MemoryHandler(BaseHandler):
    """Handler for memory CRUD operations."""

    def store(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Store content in memory.

        Args:
            args: Dict containing:
                - content (required): Content to store
                - type (required): Document type (code, note, conversation, reference)
                - source (required): Source identifier
                - tags (optional): List of tags
                - project (optional): Project name
                - language (optional): For code type, the programming language

        Returns:
            Dict with id and stored status
        """
        # Validate required fields
        content = validate_content(args.get("content"), "content")
        doc_type = validate_doc_type(args.get("type"), "type")
        source = validate_string(args.get("source"), "source", min_len=1, max_len=1000)
        tags = validate_tags(args.get("tags"), "tags")
        project = validate_project(args.get("project"), "project")

        doc_id = str(uuid.uuid4())[:16]

        # Create document
        doc = MemoryDocument(
            id=doc_id,
            content=content,
            doc_type=doc_type,
            source=source,
            project=project,
            tags=tags
        )

        # Store in SQLite (cold tier)
        self.sqlite.insert(doc)
        logger.info(f"Stored document {doc_id} of type {doc_type}")

        # Also write to vault for human access (archive tier)
        if doc_type == "code":
            self.vault.write_code_note(
                source,
                content,
                args.get("language", "text"),
                tags=tags
            )
        elif doc_type == "note":
            self.vault.write_note(
                f"notes/{doc_id}",
                content,
                {"type": "note", "source": source, "tags": tags}
            )

        # Cache in Redis if available (hot tier)
        if self.redis:
            try:
                self.redis.cache_query(content[:100], doc_id)
            except Exception as e:
                logger.debug(f"Redis cache failed: {e}")

        return {"id": doc_id, "stored": True}

    def search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search memories.

        Args:
            args: Dict containing:
                - query (required): Search query string
                - type (optional): Search type (text, semantic, hybrid)
                - limit (optional): Max results (default 10, max 100)
                - filters (optional): Dict with doc_type, project, tags filters

        Returns:
            Dict with results list and total count
        """
        query = validate_string(args.get("query"), "query", min_len=1, max_len=10000)
        search_type = args.get("type", "hybrid")
        limit = validate_limit(args.get("limit"), "limit", default=10)
        limit = min(limit, 100)  # Clamp to reasonable limit
        filters = args.get("filters", {}) or {}

        if search_type not in ["text", "semantic", "hybrid"]:
            raise ValueError(
                f"Invalid search type: {search_type}. Must be one of: text, semantic, hybrid"
            )

        logger.debug(f"Searching for: '{log_safe_query(query)}' type={search_type} limit={limit}")

        # Use TierManager for multi-tier search if available (hybrid or semantic)
        if self.tier_manager and search_type in ["hybrid", "semantic"]:
            tier_results = self.tier_manager.search_all_tiers(
                query, limit=limit * 2, search_type=search_type
            )

            # Apply filters and format results
            results = []
            for r in tier_results:
                # Filter by doc_type if specified
                if filters.get("doc_type") and r.get("type") != filters["doc_type"]:
                    continue
                # Filter by project if specified
                if filters.get("project") and r.get("project") != filters["project"]:
                    continue
                # Filter by tags if specified
                if filters.get("tags"):
                    result_tags = r.get("tags", [])
                    if not any(t in result_tags for t in filters["tags"]):
                        continue
                results.append(r)

            results = results[:limit]
            return {"results": results, "total": len(results)}

        # Fallback to SQLite-only search (text mode or no TierManager)
        results = []
        seen_ids: set = set()  # O(1) deduplication

        # Text search via SQLite FTS
        text_results = self.sqlite.search_fulltext(query, limit=limit * 2)
        for doc in text_results:
            if self._matches_filters(doc, filters):
                if doc.id not in seen_ids:
                    seen_ids.add(doc.id)
                    results.append({
                        "id": doc.id,
                        "content": doc.content[:500],
                        "type": doc.doc_type,
                        "source": doc.source,
                        "score": 1.0,
                        "match_type": "text",
                        "tier": "cold"
                    })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:limit], "total": len(results)}

    def _matches_filters(self, doc: MemoryDocument, filters: Dict[str, Any]) -> bool:
        """Check if document matches filters."""
        if not filters:
            return True
        if filters.get("doc_type") and doc.doc_type != filters["doc_type"]:
            return False
        if filters.get("project") and doc.project != filters["project"]:
            return False
        if filters.get("tags"):
            if not any(t in doc.tags for t in filters["tags"]):
                return False
        return True

    def recall(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Recall specific memory by ID.

        Args:
            args: Dict containing:
                - id (required): Document ID to recall

        Returns:
            Dict with found status and document details
        """
        doc_id = validate_string(args.get("id"), "id", min_len=1, max_len=64)
        logger.debug(f"Recalling document: {doc_id}")

        doc = self.sqlite.get(doc_id)
        if not doc:
            logger.debug(f"Document not found: {doc_id}")
            return {"found": False, "id": doc_id}

        # Track access for tier promotion (5+ accesses triggers warm tier promotion)
        if self.tier_manager:
            self.tier_manager.record_access(doc_id, len(doc.content))

        logger.debug(f"Found document: {doc_id}")
        return {
            "found": True,
            "document": {
                "id": doc.id,
                "content": doc.content,
                "type": doc.doc_type,
                "source": doc.source,
                "project": doc.project,
                "tags": doc.tags,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at
            }
        }

    def delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a memory.

        Args:
            args: Dict containing:
                - id (required): Document ID to delete

        Returns:
            Dict with deleted status and ID
        """
        doc_id = validate_string(args.get("id"), "id", min_len=1, max_len=64)
        logger.debug(f"Deleting document: {doc_id}")

        deleted = self.sqlite.delete(doc_id)
        if deleted:
            logger.info(f"Deleted document: {doc_id}")
        else:
            logger.debug(f"Document not found for deletion: {doc_id}")

        return {"deleted": deleted, "id": doc_id}

    def list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List recent memories.

        Args:
            args: Dict containing:
                - limit (optional): Max results (default 20, max 100)
                - type (optional): Filter by document type
                - project (optional): Filter by project

        Returns:
            Dict with documents list and count
        """
        limit = validate_limit(args.get("limit"), "limit", default=20)
        limit = min(limit, 100)  # Clamp to reasonable limit

        doc_type = args.get("type")
        project = args.get("project")

        # Validate if provided
        if doc_type:
            doc_type = validate_doc_type(doc_type, "type")
        if project:
            project = validate_project(project, "project")

        logger.debug(f"Listing memories: type={doc_type} project={project} limit={limit}")

        if doc_type:
            docs = self.sqlite.search_by_type(doc_type, limit)
        elif project:
            docs = self.sqlite.search_by_project(project, limit)
        else:
            docs = self.sqlite.get_recent(limit)

        logger.debug(f"Found {len(docs)} memories")

        return {
            "documents": [{
                "id": d.id,
                "type": d.doc_type,
                "source": d.source,
                "preview": d.content[:200],
                "updated_at": d.updated_at
            } for d in docs],
            "count": len(docs)
        }
