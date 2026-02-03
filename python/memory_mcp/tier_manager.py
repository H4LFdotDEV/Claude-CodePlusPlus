# tier_manager.py
# Orchestrates data flow between memory tiers
# Jeremiah Kroesche | Halfservers LLC

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from .access_tracker import AccessTracker
from .stats_collector import record
from .async_utils import run_async
from shared.log_utils import log_safe_query
from .config import MemoryConfig

if TYPE_CHECKING:
    from .redis_client import RedisClient
    from .graphiti_manager import GraphitiManager
    from .livegrep_client import LivegrepClient
    from .sqlite_index import SQLiteIndex

logger = logging.getLogger("memory_mcp")

# Constants for timeouts and limits
GRAPHITI_TIMEOUT_SECONDS = 30.0
PROMOTION_TIMEOUT_SECONDS = 60.0


@dataclass
class TierPromotionConfig:
    """Configuration for tier promotion/demotion."""

    # Access count to trigger promotion to warm tier
    promotion_threshold: int = 5

    # Minimum content size for entity extraction (bytes)
    min_size_for_extraction: int = 100

    # Hours without access before demotion
    demotion_ttl_hours: int = 168  # 1 week

    # Maximum items in hot tier
    hot_tier_max_items: int = 1000


class TierManager:
    """Orchestrates data flow between memory tiers.

    Tiers:
    - Hot: Redis (session cache, <1ms access)
    - Warm: Graphiti/Neo4j (knowledge graph, <50ms)
    - Cold: SQLite FTS (full-text search, <100ms)
    - Cold: livegrep (code search, optional)
    - Archive: Obsidian vault (human-readable)
    """

    def __init__(
        self,
        redis: Optional["RedisClient"] = None,
        graphiti: Optional["GraphitiManager"] = None,
        livegrep: Optional["LivegrepClient"] = None,
        sqlite: Optional["SQLiteIndex"] = None,
        vault: Optional[Any] = None,
        config: Optional[TierPromotionConfig] = None,
        memory_config: Optional[MemoryConfig] = None
    ):
        self.redis = redis
        self.graphiti = graphiti
        self.livegrep = livegrep
        self.sqlite = sqlite
        self.vault = vault
        self.config = config or TierPromotionConfig()
        self.memory_config = memory_config
        self._access_tracker = AccessTracker(redis_client=redis)

    def _validate_content_size(self, content: str, operation: str = "storage") -> None:
        """Validate content size is within limits to prevent OOM attacks.

        Args:
            content: Content to validate
            operation: Type of operation ("storage" or "entity_extraction")

        Raises:
            ValueError: If content exceeds size limits
        """
        if not self.memory_config:
            # No config available, skip validation
            return

        size = len(content.encode('utf-8'))

        if operation == "storage":
            max_size = self.memory_config.max_content_size
            if size > max_size:
                raise ValueError(
                    f"Content size {size:,} bytes exceeds maximum {max_size:,} bytes "
                    f"for {operation}. This limit prevents out-of-memory attacks."
                )
        elif operation == "entity_extraction":
            max_size = self.memory_config.max_entity_extraction_size
            if size > max_size:
                logger.warning(
                    f"Content size {size:,} bytes exceeds entity extraction limit "
                    f"{max_size:,} bytes. Skipping entity extraction."
                )
                raise ValueError(
                    f"Content too large for entity extraction ({size:,} > {max_size:,} bytes)"
                )

    def should_promote_to_warm(self, doc_id: str) -> bool:
        """Check if document should be promoted from cold to warm tier.

        Args:
            doc_id: Document ID to check

        Returns:
            True if document should be promoted
        """
        if not self.graphiti:
            return False

        stats = self._access_tracker.get_stats(doc_id)
        return (
            stats.access_count >= self.config.promotion_threshold and
            stats.content_size >= self.config.min_size_for_extraction
        )

    def promote_to_warm(self, doc_id: str) -> bool:
        """Extract entities and store in Graphiti knowledge graph.

        Args:
            doc_id: Document ID to promote

        Returns:
            True if promotion succeeded
        """
        if not self.graphiti or not self.sqlite:
            return False

        start = time.time()
        try:
            doc = self.sqlite.get(doc_id)
            if not doc:
                return False

            # Validate content size before entity extraction (security: prevent OOM)
            try:
                self._validate_content_size(doc.content, operation="entity_extraction")
            except ValueError as e:
                # Content too large for entity extraction - skip promotion
                logger.info(f"Skipping promotion of {doc_id}: {e}")
                return False

            # Add to knowledge graph using shared async utility with timeout
            run_async(
                self.graphiti.add_memory(
                    content=doc.content,
                    source=doc.source,
                    doc_type=doc.doc_type
                ),
                timeout=PROMOTION_TIMEOUT_SECONDS
            )

            latency_ms = (time.time() - start) * 1000
            record("graphiti", latency_ms, success=True)
            logger.info(f"Promoted document {doc_id} to warm tier")
            return True

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            record("graphiti", latency_ms, success=False)
            logger.warning(f"Failed to promote {doc_id}: {e}")
            return False

    def search_all_tiers(
        self,
        query: str,
        limit: int = 20,
        search_type: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """Coordinate search across all tiers with deduplication.

        Args:
            query: Search query
            limit: Maximum results to return
            search_type: "text", "semantic", or "hybrid"

        Returns:
            List of search results from all tiers
        """
        results: List[Dict[str, Any]] = []
        seen_ids: set = set()

        # Tier 1: Hot (Redis cache)
        if self.redis:
            start = time.time()
            try:
                cached = self._search_redis_cache(query)
                latency_ms = (time.time() - start) * 1000
                record("redis", latency_ms, success=True)

                for r in cached:
                    if r.get("id") not in seen_ids:
                        r["tier"] = "hot"
                        results.append(r)
                        seen_ids.add(r["id"])
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                record("redis", latency_ms, success=False)
                logger.debug(f"Redis search failed: {e}")

        # Tier 2: Warm (Graphiti knowledge graph)
        if self.graphiti and len(results) < limit:
            start = time.time()
            try:
                entities = self._search_graphiti(query, limit - len(results))
                latency_ms = (time.time() - start) * 1000
                record("graphiti", latency_ms, success=True)

                for e in entities:
                    entity_id = str(e.get("uuid", e.get("id", "")))
                    if entity_id and entity_id not in seen_ids:
                        results.append(self._entity_to_result(e))
                        seen_ids.add(entity_id)
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                record("graphiti", latency_ms, success=False)
                logger.debug(f"Graphiti search failed: {e}")

        # Tier 3: Cold (SQLite FTS)
        if self.sqlite and len(results) < limit:
            start = time.time()
            try:
                docs = self.sqlite.search_fulltext(query, limit=limit - len(results))
                latency_ms = (time.time() - start) * 1000
                record("sqlite", latency_ms, success=True)

                for d in docs:
                    if d.id not in seen_ids:
                        results.append(self._doc_to_result(d))
                        seen_ids.add(d.id)
                        # Track access for promotion
                        self._access_tracker.record_access(d.id, len(d.content))
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                record("sqlite", latency_ms, success=False)
                logger.debug(f"SQLite search failed: {e}")

        # Tier 4: Cold (livegrep code search) - optional
        if self.livegrep and len(results) < limit:
            start = time.time()
            try:
                code_results = self._search_livegrep(query, limit - len(results))
                latency_ms = (time.time() - start) * 1000
                record("livegrep", latency_ms, success=True)

                for r in code_results:
                    result_id = f"livegrep:{r.get('path', '')}:{r.get('line_number', 0)}"
                    if result_id not in seen_ids:
                        results.append(r)
                        seen_ids.add(result_id)
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                record("livegrep", latency_ms, success=False)
                logger.debug(f"livegrep search failed: {e}")

        return results[:limit]

    def record_access(self, doc_id: str, content_size: int = 0) -> None:
        """Record a document access for promotion tracking.

        Args:
            doc_id: Document ID
            content_size: Size of content in bytes
        """
        self._access_tracker.record_access(doc_id, content_size)

        # Check if document should be promoted
        if self.should_promote_to_warm(doc_id):
            self.promote_to_warm(doc_id)

    def get_tier_stats(self) -> Dict[str, Any]:
        """Get statistics for all tiers.

        Returns:
            Dict with tier availability and stats
        """
        from .stats_collector import get_collector

        stats = get_collector().get_stats()

        return {
            "tiers": {
                "hot": {
                    "available": self.redis is not None,
                    "stats": stats.get("redis", {})
                },
                "warm": {
                    "available": self.graphiti is not None,
                    "stats": stats.get("graphiti", {})
                },
                "cold": {
                    "available": self.sqlite is not None,
                    "stats": stats.get("sqlite", {})
                },
                "code_search": {
                    "available": self.livegrep is not None,
                    "stats": stats.get("livegrep", {})
                },
                "archive": {
                    "available": self.vault is not None,
                    "stats": {}
                }
            },
            "hot_documents": len(self._access_tracker.get_hot_documents(
                threshold=self.config.promotion_threshold
            ))
        }

    async def search_all_tiers_parallel(
        self,
        query: str,
        limit: int = 10,
        tiers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search all tiers concurrently and merge results.

        This provides significant performance improvements over sequential search by:
        - Running all tier searches in parallel using asyncio.gather
        - Gracefully handling failures in individual tiers
        - Merging and deduplicating results by ID
        - Sorting by relevance score

        Args:
            query: Search query string
            limit: Maximum results to return
            tiers: Optional list of tiers to search ['hot', 'warm', 'cold', 'archive']

        Returns:
            Merged and deduplicated search results sorted by relevance
        """
        tiers = tiers or ['hot', 'warm', 'cold', 'archive']

        # Create search tasks for each tier
        tasks = []
        tier_names = []

        for tier in tiers:
            if tier == 'hot' and self.redis:
                tasks.append(self._search_hot_tier(query, limit))
                tier_names.append('hot')
            elif tier == 'warm' and self.graphiti:
                tasks.append(self._search_warm_tier(query, limit))
                tier_names.append('warm')
            elif tier == 'cold' and self.sqlite:
                tasks.append(self._search_cold_tier(query, limit))
                tier_names.append('cold')
            elif tier == 'archive' and self.vault:
                tasks.append(self._search_archive_tier(query, limit))
                tier_names.append('archive')

        if not tasks:
            logger.debug("No tiers available for parallel search")
            return []

        # Execute all searches concurrently with fault tolerance
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_latency_ms = (time.time() - start_time) * 1000

        # Merge and deduplicate
        all_results = []
        seen_ids = set()
        tier_stats = {}

        for tier_name, tier_results in zip(tier_names, results):
            if isinstance(tier_results, Exception):
                tier_stats[tier_name] = {"error": str(tier_results), "count": 0}
                logger.warning(f"{tier_name} tier search failed: {tier_results}")
                continue

            tier_count = 0
            for result in (tier_results or []):
                result_id = result.get('id') or result.get('doc_id')
                if result_id and result_id not in seen_ids:
                    seen_ids.add(result_id)
                    result['_source_tier'] = tier_name
                    all_results.append(result)
                    tier_count += 1

            tier_stats[tier_name] = {"count": tier_count}

        # Sort by relevance score (higher is better)
        all_results.sort(
            key=lambda r: r.get('score', r.get('relevance', 0)),
            reverse=True
        )

        # Log performance
        logger.debug(
            f"Parallel search completed in {total_latency_ms:.1f}ms, "
            f"found {len(all_results)} unique results from {tier_stats}"
        )

        return all_results[:limit]

    async def _search_hot_tier(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Redis hot tier.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results from hot tier
        """
        if not self.redis:
            return []
        try:
            return await asyncio.to_thread(
                self._search_redis_cache, query
            )
        except Exception as e:
            logger.warning(f"Hot tier search failed: {e}")
            raise

    async def _search_warm_tier(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Graphiti warm tier.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results from warm tier
        """
        if not self.graphiti:
            return []
        try:
            # _search_graphiti uses run_async internally, so we need to run in thread
            return await asyncio.to_thread(
                self._search_graphiti, query, limit
            )
        except Exception as e:
            logger.warning(f"Warm tier search failed: {e}")
            raise

    async def _search_cold_tier(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search SQLite cold tier.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results from cold tier
        """
        if not self.sqlite:
            return []
        try:
            docs = await asyncio.to_thread(
                self.sqlite.search_fulltext, query, limit
            )
            return [self._doc_to_result(d) for d in docs]
        except Exception as e:
            logger.warning(f"Cold tier search failed: {e}")
            raise

    async def _search_archive_tier(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Vault archive tier.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results from archive tier
        """
        if not self.vault:
            return []
        try:
            notes = await asyncio.to_thread(
                self.vault.search_notes, query
            )
            # Convert VaultNote objects to dict format
            return [
                {
                    'id': note.id,
                    'content': note.content[:500],
                    'type': 'note',
                    'source': note.path,
                    'score': 0.6,  # Archive tier gets lower base score
                    'tier': 'archive',
                    'match_type': 'text',
                    'title': note.title,
                    'tags': note.tags
                }
                for note in notes[:limit]
            ]
        except Exception as e:
            logger.warning(f"Archive tier search failed: {e}")
            raise

    def _search_redis_cache(self, query: str) -> List[Dict]:
        """Search Redis cache for cached query results."""
        if not self.redis:
            return []

        try:
            cached = self.redis.get_cached_query(query)
            return cached or []
        except Exception:
            return []

    def _search_graphiti(self, query: str, limit: int) -> List[Dict]:
        """Search Graphiti knowledge graph."""
        if not self.graphiti:
            return []

        try:
            # Use shared async utility with timeout
            entities = run_async(
                self.graphiti.search_entities(query, limit=limit),
                timeout=GRAPHITI_TIMEOUT_SECONDS
            )
            return [
                {
                    "uuid": e.id,
                    "id": e.id,
                    "name": e.name,
                    "summary": e.summary,
                    "labels": e.labels,
                    "source_description": "graphiti"
                }
                for e in entities
            ]
        except Exception as e:
            logger.debug(f"Graphiti search failed: {e}")
            return []

    def _search_livegrep(self, query: str, limit: int) -> List[Dict]:
        """Search livegrep code index."""
        if not self.livegrep:
            return []

        try:
            response = self.livegrep.search(query, max_matches=limit)
            # LivegrepSearchResponse is a dataclass, not a dict
            return [
                {
                    "repo": r.repo,
                    "path": r.path,
                    "line_number": r.line_number,
                    "line": r.line_content,
                    "tier": "cold"
                }
                for r in response.results
            ]
        except Exception as e:
            logger.debug(f"livegrep search failed: {e}")
            return []

    def _entity_to_result(self, entity: Dict) -> Dict[str, Any]:
        """Convert Graphiti entity to search result format."""
        return {
            "id": str(entity.get("uuid", entity.get("id", ""))),
            "content": entity.get("name", "") + "\n" + entity.get("summary", ""),
            "type": "entity",
            "source": entity.get("source_description", "graphiti"),
            "score": entity.get("score", 0.8),
            "tier": "warm",
            "match_type": "semantic"
        }

    def _doc_to_result(self, doc) -> Dict[str, Any]:
        """Convert SQLite document to search result format."""
        return {
            "id": doc.id,
            "content": doc.content[:500],
            "type": doc.doc_type,
            "source": doc.source,
            "score": 0.7,
            "tier": "cold",
            "match_type": "text"
        }
