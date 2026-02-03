# graphiti_manager.py
# Knowledge Graph Manager for Claude Code++ Memory System (Warm Tier)
# Jeremiah Kroesche | Halfservers LLC
#
# Uses Graphiti (by Zep AI) for temporal knowledge graph operations.
# Provides entity extraction, relationship mapping, and temporal queries.

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from shared.log_utils import log_safe_query

logger = logging.getLogger(__name__)

# Check if graphiti-core is available
try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    logger.info("graphiti-core not installed. Install with: pip install graphiti-core")


@dataclass
class EntityResult:
    """Result from entity search."""
    id: str
    name: str
    summary: str
    labels: List[str]
    created_at: Optional[str] = None


@dataclass
class FactResult:
    """Result from fact/relationship search."""
    id: str
    source_entity: str
    target_entity: str
    fact: str
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None


@dataclass
class EpisodeResult:
    """Result from adding an episode."""
    episode_id: str
    entities_extracted: int
    relationships_extracted: int


class GraphitiManager:
    """
    Knowledge graph manager using Graphiti/Neo4j.

    Graphiti provides:
    - Automatic entity extraction from text
    - Relationship discovery between entities
    - Temporal awareness (when facts were true)
    - Hybrid search (semantic + keyword + graph traversal)

    Usage:
        manager = GraphitiManager()
        await manager.initialize()

        # Add content (extracts entities/relationships automatically)
        result = await manager.add_memory(
            content="Claude is an AI assistant created by Anthropic.",
            source="documentation",
            doc_type="note"
        )

        # Search for entities
        entities = await manager.search_entities("Claude")

        # Search for facts/relationships
        facts = await manager.search_facts("AI assistant")

    Security:
        Credentials are accessed via properties that read from environment
        on each access, rather than stored as instance attributes. This
        prevents credential exposure via object inspection.
    """

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        openai_api_key: str = None
    ):
        """
        Initialize Graphiti manager.

        Args:
            uri: Neo4j Bolt URI (default: bolt://localhost:7687)
            user: Neo4j username (default: neo4j)
            password: Neo4j password (from NEO4J_PASSWORD env var)
            openai_api_key: OpenAI API key for entity extraction (from OPENAI_API_KEY env var)

        Note:
            Password and API key overrides are stored in environment variables
            prefixed with _GRAPHITI_OVERRIDE_ for testing purposes, not as
            instance attributes.
        """
        # Non-sensitive config can be stored as attributes
        self._uri_override = uri
        self._user_override = user

        # Sensitive credentials: store overrides in environment, not instance
        # This allows testing while preventing credential exposure via inspection
        if password is not None:
            os.environ["_GRAPHITI_OVERRIDE_PASSWORD"] = password
        if openai_api_key is not None:
            os.environ["_GRAPHITI_OVERRIDE_OPENAI_KEY"] = openai_api_key

        self._graphiti: Optional["Graphiti"] = None
        self._initialized = False
        self._init_lock: Optional[asyncio.Lock] = None  # Lazily initialized

        if not GRAPHITI_AVAILABLE:
            logger.warning("Graphiti not available - knowledge graph features disabled")

    @property
    def uri(self) -> str:
        """Neo4j Bolt URI."""
        return self._uri_override or os.environ.get("NEO4J_URI", "bolt://localhost:7687")

    @property
    def user(self) -> str:
        """Neo4j username."""
        return self._user_override or os.environ.get("NEO4J_USER", "neo4j")

    @property
    def _password(self) -> Optional[str]:
        """
        Neo4j password - read from environment on each access.

        Security: Not stored as instance attribute to prevent exposure
        via object inspection.
        """
        return (
            os.environ.get("_GRAPHITI_OVERRIDE_PASSWORD") or
            os.environ.get("NEO4J_PASSWORD")
        )

    @property
    def _openai_api_key(self) -> Optional[str]:
        """
        OpenAI API key - read from environment on each access.

        Security: Not stored as instance attribute to prevent exposure
        via object inspection.
        """
        return (
            os.environ.get("_GRAPHITI_OVERRIDE_OPENAI_KEY") or
            os.environ.get("OPENAI_API_KEY")
        )

    def _get_init_lock(self) -> asyncio.Lock:
        """
        Get or create the async initialization lock.

        SECURITY: Uses asyncio.Lock instead of threading.Lock to prevent
        deadlocks when awaiting inside the lock context. threading.Lock
        blocks the entire thread, while asyncio.Lock properly yields
        control to other coroutines.
        """
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        return self._init_lock

    async def initialize(self) -> bool:
        """
        Initialize Graphiti connection and build indices.

        Uses asyncio.Lock for thread-safe async initialization.

        Returns:
            True if initialization successful, False otherwise
        """
        # Fast path - no lock needed if already initialized
        if self._initialized:
            return True

        if not GRAPHITI_AVAILABLE:
            logger.warning("Cannot initialize: graphiti-core not installed")
            return False

        if not self._password:
            logger.warning("Cannot initialize: NEO4J_PASSWORD not set")
            return False

        # Use async lock for proper coroutine-safe locking
        async with self._get_init_lock():
            # Double-check after acquiring lock
            if self._initialized:
                return True

            try:
                # Initialize Graphiti
                self._graphiti = Graphiti(
                    uri=self.uri,
                    user=self.user,
                    password=self._password
                )

                # Build indices and constraints
                await self._graphiti.build_indices_and_constraints()

                self._initialized = True
                logger.info(f"Graphiti initialized: {self.uri}")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize Graphiti: {e}")
                self._graphiti = None
                return False

    async def add_memory(
        self,
        content: str,
        source: str,
        doc_type: str,
        reference_time: Optional[datetime] = None,
        group_id: Optional[str] = None
    ) -> Optional[EpisodeResult]:
        """
        Add content to knowledge graph, extracting entities and relationships.
        
        Args:
            content: Text content to process
            source: Source identifier (e.g., filename, URL, tool name)
            doc_type: Document type (code, note, conversation, reference)
            reference_time: When the content was created/relevant
            group_id: Optional group ID for multi-tenant isolation
            
        Returns:
            EpisodeResult with extraction statistics, or None on failure
        """
        if not await self.initialize():
            return None
            
        try:
            # Map doc_type to episode type
            episode_type_map = {
                "code": EpisodeType.text,
                "note": EpisodeType.text,
                "conversation": EpisodeType.message,
                "reference": EpisodeType.text,
            }
            episode_type = episode_type_map.get(doc_type, EpisodeType.text)
            
            # Add episode to graph
            episode = await self._graphiti.add_episode(
                name=f"{doc_type}:{source}",
                episode_body=content,
                episode_type=episode_type,
                source_description=source,
                reference_time=reference_time or datetime.now(timezone.utc),
                group_id=group_id
            )
            
            # Count extracted entities and relationships
            # Note: Graphiti handles extraction internally
            entities_count = len(episode.entity_edges) if hasattr(episode, 'entity_edges') else 0
            
            logger.debug(f"Added episode {episode.uuid}: {entities_count} entities extracted")
            
            return EpisodeResult(
                episode_id=episode.uuid,
                entities_extracted=entities_count,
                relationships_extracted=0  # TODO: Get actual count
            )
            
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    async def add_memory_bulk(
        self,
        items: List[Dict[str, Any]],
        group_id: Optional[str] = None
    ) -> List[EpisodeResult]:
        """
        Add multiple content items efficiently.
        
        Args:
            items: List of dicts with keys: content, source, doc_type, reference_time
            group_id: Optional group ID for multi-tenant isolation
            
        Returns:
            List of EpisodeResult for each item
        """
        if not await self.initialize():
            return []
            
        results = []
        for item in items:
            result = await self.add_memory(
                content=item.get("content", ""),
                source=item.get("source", "unknown"),
                doc_type=item.get("doc_type", "note"),
                reference_time=item.get("reference_time"),
                group_id=group_id
            )
            if result:
                results.append(result)
                
        return results

    async def search_entities(
        self,
        query: str,
        limit: int = 10,
        group_id: Optional[str] = None
    ) -> List[EntityResult]:
        """
        Search for entity nodes matching query.
        
        Uses hybrid search combining semantic similarity, keyword matching,
        and graph structure.
        
        Args:
            query: Search query
            limit: Maximum results to return
            group_id: Optional group ID for filtering
            
        Returns:
            List of matching entities
        """
        if not await self.initialize():
            return []
            
        try:
            nodes = await self._graphiti.search_nodes(
                query=query,
                group_ids=[group_id] if group_id else None
            )
            
            results = []
            for node in nodes[:limit]:
                results.append(EntityResult(
                    id=node.uuid,
                    name=node.name,
                    summary=node.summary or "",
                    labels=node.labels if hasattr(node, 'labels') else [],
                    created_at=node.created_at.isoformat() if hasattr(node, 'created_at') else None
                ))
                
            logger.debug(f"Entity search '{log_safe_query(query)}': {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Entity search failed: {e}")
            return []

    async def search_facts(
        self,
        query: str,
        limit: int = 10,
        group_id: Optional[str] = None
    ) -> List[FactResult]:
        """
        Search for facts/relationships matching query.
        
        Args:
            query: Search query
            limit: Maximum results to return
            group_id: Optional group ID for filtering
            
        Returns:
            List of matching facts
        """
        if not await self.initialize():
            return []
            
        try:
            edges = await self._graphiti.search_edges(
                query=query,
                group_ids=[group_id] if group_id else None
            )
            
            results = []
            for edge in edges[:limit]:
                results.append(FactResult(
                    id=edge.uuid,
                    source_entity=edge.source_node_name if hasattr(edge, 'source_node_name') else "",
                    target_entity=edge.target_node_name if hasattr(edge, 'target_node_name') else "",
                    fact=edge.fact if hasattr(edge, 'fact') else str(edge),
                    valid_at=edge.valid_at.isoformat() if hasattr(edge, 'valid_at') and edge.valid_at else None,
                    invalid_at=edge.invalid_at.isoformat() if hasattr(edge, 'invalid_at') and edge.invalid_at else None
                ))
                
            logger.debug(f"Fact search '{log_safe_query(query)}': {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Fact search failed: {e}")
            return []

    async def get_entity(self, entity_id: str) -> Optional[EntityResult]:
        """
        Get a specific entity by ID.
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            EntityResult or None if not found
        """
        if not await self.initialize():
            return None
            
        try:
            # Note: Graphiti may need a specific method for this
            # For now, search by ID
            node = await self._graphiti.get_node(entity_id)
            if node:
                return EntityResult(
                    id=node.uuid,
                    name=node.name,
                    summary=node.summary or "",
                    labels=node.labels if hasattr(node, 'labels') else []
                )
            return None
            
        except Exception as e:
            logger.debug(f"Get entity failed: {e}")
            return None

    async def get_related_entities(
        self,
        entity_name: str,
        relationship_type: Optional[str] = None,
        limit: int = 10
    ) -> List[EntityResult]:
        """
        Get entities related to a given entity via graph traversal.
        
        Args:
            entity_name: Name of the entity to start from
            relationship_type: Optional filter by relationship type
            limit: Maximum results
            
        Returns:
            List of related entities
        """
        if not await self.initialize():
            return []
            
        try:
            # Use Cypher query for graph traversal
            # This is a simplified version - Graphiti may have better methods
            query = f"Related to {entity_name}"
            if relationship_type:
                query += f" ({relationship_type})"
                
            return await self.search_entities(query, limit=limit)
            
        except Exception as e:
            logger.error(f"Get related entities failed: {e}")
            return []

    async def delete_episode(self, episode_id: str) -> bool:
        """
        Delete an episode and its extracted entities/relationships.
        
        Args:
            episode_id: Episode UUID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if not await self.initialize():
            return False
            
        try:
            # Note: Check Graphiti API for proper deletion method
            # This may cascade to entities/relationships
            await self._graphiti.delete_episode(episode_id)
            logger.debug(f"Deleted episode: {episode_id}")
            return True
            
        except Exception as e:
            logger.error(f"Delete episode failed: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check Neo4j/Graphiti connection health.
        
        Returns:
            True if healthy, False otherwise
        """
        if not GRAPHITI_AVAILABLE:
            return False
            
        if not self._graphiti:
            return False
            
        try:
            # Run a simple query to test connection
            # This is synchronous for quick health checks
            return True  # TODO: Implement actual Neo4j ping
            
        except Exception as e:
            logger.debug(f"Graphiti health check failed: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge graph statistics.
        
        Returns:
            Dict with entity count, fact count, etc.
        """
        if not await self.initialize():
            return {
                "available": False,
                "error": "Not initialized"
            }
            
        try:
            # Query Neo4j for counts
            # This would use Cypher queries
            return {
                "available": True,
                "initialized": self._initialized,
                "uri": self.uri,
                # TODO: Add actual counts from Neo4j
                "entity_count": -1,
                "fact_count": -1,
                "episode_count": -1
            }
            
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }

    async def close(self):
        """Close the Graphiti connection (async-safe)."""
        async with self._get_init_lock():
            if self._graphiti:
                try:
                    await self._graphiti.close()
                except Exception as e:
                    logger.debug(f"Error closing Graphiti: {e}")
                finally:
                    self._graphiti = None
                    self._initialized = False
