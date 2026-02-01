# tier_manager.py
# Orchestrates data flow between memory tiers
# Jeremiah Kroesche | Halfservers LLC

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from .access_tracker import AccessTracker
from .stats_collector import record

if TYPE_CHECKING:
    from .redis_client import RedisClient
    from .graphiti_manager import GraphitiManager
    from .livegrep_client import LivegrepClient
    from .sqlite_index import SQLiteIndex

logger = logging.getLogger("memory_mcp")


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
        config: Optional[TierPromotionConfig] = None
    ):
        self.redis = redis
        self.graphiti = graphiti
        self.livegrep = livegrep
        self.sqlite = sqlite
        self.config = config or TierPromotionConfig()
        self._access_tracker = AccessTracker(redis_client=redis)

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

            # Add to knowledge graph
            self.graphiti.add_episode(
                name=f"memory:{doc_id}",
                episode_body=doc.content,
                source_description=doc.source
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
                }
            },
            "hot_documents": len(self._access_tracker.get_hot_documents(
                threshold=self.config.promotion_threshold
            ))
        }

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
            return self.graphiti.search(query, limit=limit)
        except Exception:
            return []

    def _search_livegrep(self, query: str, limit: int) -> List[Dict]:
        """Search livegrep code index."""
        if not self.livegrep:
            return []

        try:
            result = self.livegrep.search(query, max_matches=limit)
            return result.get("results", [])
        except Exception:
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
