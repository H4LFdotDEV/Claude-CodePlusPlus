# redis_client.py
# Redis Client for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Hot memory layer - session state, recent queries, templates
# SECURITY: Uses Pydantic models for safe JSON deserialization

import json
import hashlib
import logging
import threading
import time
from typing import Optional, Dict, Any, List, Iterator
from datetime import datetime, timezone

try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    RedisConnectionError = ConnectionError  # Fallback for type hints

from pydantic import ValidationError

from .config import get_config, RedisConfig
from shared.log_utils import log_safe_query
from .schemas import (
    SessionStateModel,
    TemplateCacheModel,
    QueryCacheModel,
    EmbeddingCacheModel,
    ContextWindowItemModel,
)

logger = logging.getLogger(__name__)


# ============================================================================
# BACKWARD COMPATIBILITY LAYER
# ============================================================================

class SessionState:
    """
    Session state class for backward compatibility.

    SECURITY NOTE: This is a legacy interface. New code should use
    SessionStateModel from schemas.py instead.
    """

    def __init__(
        self,
        session_id: str,
        project_path: str,
        active_files: List[str],
        recent_queries: List[str],
        context_window: List[Dict[str, Any]],
        created_at: str,
        updated_at: str,
    ):
        self.session_id = session_id
        self.project_path = project_path
        self.active_files = active_files
        self.recent_queries = recent_queries
        self.context_window = context_window
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "active_files": self.active_files,
            "recent_queries": self.recent_queries,
            "context_window": self.context_window,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Create from dict (VALIDATED via Pydantic)."""
        # Validate using Pydantic model first
        validated = SessionStateModel(**data)
        # Convert back to dict for backward compat
        return cls(
            session_id=validated.session_id,
            project_path=validated.project_path,
            active_files=validated.active_files,
            recent_queries=validated.recent_queries,
            context_window=[
                msg.model_dump() for msg in validated.context_window
            ],
            created_at=validated.created_at,
            updated_at=validated.updated_at,
        )


class CachedQuery:
    """
    Cached query result class.

    SECURITY NOTE: This is a legacy interface.
    """

    def __init__(
        self,
        query: str,
        result: Any,
        embedding: Optional[List[float]],
        created_at: str,
        hits: int = 0,
    ):
        self.query = query
        self.result = result
        self.embedding = embedding
        self.created_at = created_at
        self.hits = hits


class RedisClient:
    """Redis client for hot memory layer with connection retry and thread safety."""

    # Key prefixes
    PREFIX_SESSION = "cc:session:"
    PREFIX_TEMPLATE = "cc:template:"
    PREFIX_QUERY = "cc:query:"
    PREFIX_EMBEDDING = "cc:embed:"
    PREFIX_CONTEXT = "cc:context:"

    # Connection retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 0.5  # Exponential backoff base (seconds)

    def __init__(self, config: Optional[RedisConfig] = None):
        if not REDIS_AVAILABLE:
            raise ImportError("redis is not installed. Run: pip install redis")

        self.config = config or get_config().redis
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._lock = threading.Lock()  # Thread safety for connection state

    def connect(self, retries: int = None) -> bool:
        """
        Connect to Redis server with retry logic.

        Args:
            retries: Number of retry attempts (default: MAX_RETRIES)

        Returns:
            True if connected successfully, False otherwise
        """
        if retries is None:
            retries = self.MAX_RETRIES

        with self._lock:
            for attempt in range(retries + 1):
                try:
                    self._client = redis.Redis(
                        host=self.config.host,
                        port=self.config.port,
                        db=self.config.db,
                        password=self.config.password,
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=30,  # Auto-reconnect
                    )
                    # Test connection
                    self._client.ping()
                    self._connected = True
                    if attempt > 0:
                        logger.info(f"Redis connected after {attempt + 1} attempts")
                    return True
                except (redis.ConnectionError, RedisConnectionError) as e:
                    self._connected = False
                    if attempt < retries:
                        delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                        logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Redis connection failed after {retries + 1} attempts: {e}")
            return False

    def disconnect(self):
        """Disconnect from Redis (thread-safe)."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    logger.debug(f"Error closing Redis connection: {e}")
                finally:
                    self._client = None
                    self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if not self._connected or not self._client:
            return False
        try:
            self._client.ping()
            return True
        except redis.ConnectionError:
            self._connected = False
            return False

    def _ensure_connected(self):
        """Ensure we're connected to Redis."""
        if not self.is_connected:
            if not self.connect():
                raise ConnectionError("Could not connect to Redis")

    # Session Management

    def save_session(self, session: SessionState) -> bool:
        """Save session state."""
        self._ensure_connected()
        key = f"{self.PREFIX_SESSION}{session.session_id}"
        session.updated_at = datetime.now(timezone.utc).isoformat()

        try:
            self._client.setex(
                key,
                self.config.ttl_session,
                json.dumps(session.to_dict())
            )
            return True
        except redis.RedisError:
            return False

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Retrieve and validate session state.

        SECURITY: Validates session data using Pydantic schema before
        deserializing to SessionState object. Prevents injection attacks
        and ensures data integrity.

        Args:
            session_id: Session identifier to retrieve

        Returns:
            SessionState object if found and valid, None otherwise

        Raises:
            ConnectionError: If Redis is not connected
        """
        self._ensure_connected()
        key = f"{self.PREFIX_SESSION}{session_id}"

        try:
            data = self._client.get(key)
            if data is None:
                return None

            # Parse JSON
            try:
                raw_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse session JSON for %s: %s",
                    session_id,
                    e,
                    extra={"key": key}
                )
                return None

            # Validate using Pydantic schema
            try:
                validated = SessionStateModel(**raw_data)
                return SessionState.from_dict(validated.model_dump())
            except ValidationError as e:
                logger.error(
                    "Session data validation failed for %s: %s",
                    session_id,
                    e,
                    extra={"key": key, "errors": e.errors()}
                )
                return None

        except redis.RedisError as e:
            logger.error(
                "Redis error retrieving session %s: %s",
                session_id,
                e,
                extra={"key": key}
            )
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete session state."""
        self._ensure_connected()
        key = f"{self.PREFIX_SESSION}{session_id}"
        return self._client.delete(key) > 0

    def _scan_keys(self, pattern: str) -> Iterator[str]:
        """
        Iterate over keys matching pattern using SCAN (non-blocking).

        SCAN is O(1) per call and doesn't block Redis, unlike KEYS which is O(N)
        and blocks the entire server. Essential for production use.
        """
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                yield key
            if cursor == 0:
                break

    def list_sessions(self) -> List[str]:
        """List all active session IDs using non-blocking SCAN."""
        self._ensure_connected()
        pattern = f"{self.PREFIX_SESSION}*"
        return [k.replace(self.PREFIX_SESSION, "") for k in self._scan_keys(pattern)]

    # Template Caching

    def cache_template(self, name: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Cache a prompt template."""
        self._ensure_connected()
        key = f"{self.PREFIX_TEMPLATE}{name}"

        data = {
            "content": content,
            "metadata": metadata or {},
            "cached_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            self._client.setex(
                key,
                self.config.ttl_templates,
                json.dumps(data)
            )
            return True
        except redis.RedisError:
            return False

    def get_template(self, name: str) -> Optional[str]:
        """
        Get and validate cached template content.

        SECURITY: Validates template data using Pydantic schema before
        extracting content. Prevents malformed data from causing issues.

        Args:
            name: Template name/identifier

        Returns:
            Template content string if found and valid, None otherwise

        Raises:
            ConnectionError: If Redis is not connected
        """
        self._ensure_connected()
        key = f"{self.PREFIX_TEMPLATE}{name}"

        try:
            data = self._client.get(key)
            if data is None:
                return None

            # Parse JSON
            try:
                raw_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse template JSON for %s: %s",
                    name,
                    e,
                    extra={"key": key}
                )
                return None

            # Validate using Pydantic schema
            try:
                validated = TemplateCacheModel(**raw_data)
                return validated.content
            except ValidationError as e:
                logger.error(
                    "Template data validation failed for %s: %s",
                    name,
                    e,
                    extra={"key": key, "errors": e.errors()}
                )
                return None

        except redis.RedisError as e:
            logger.error(
                "Redis error retrieving template %s: %s",
                name,
                e,
                extra={"key": key}
            )
            return None

    def list_templates(self) -> List[str]:
        """List all cached template names using non-blocking SCAN."""
        self._ensure_connected()
        pattern = f"{self.PREFIX_TEMPLATE}*"
        return [k.replace(self.PREFIX_TEMPLATE, "") for k in self._scan_keys(pattern)]

    # Query Caching

    def _query_hash(self, query: str) -> str:
        """Generate hash for query."""
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    def cache_query(self, query: str, result: Any, embedding: Optional[List[float]] = None) -> bool:
        """Cache a query result."""
        self._ensure_connected()
        query_hash = self._query_hash(query)
        key = f"{self.PREFIX_QUERY}{query_hash}"

        data = {
            "query": query,
            "result": result,
            "embedding": embedding,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "hits": 0
        }

        try:
            self._client.setex(
                key,
                self.config.ttl_queries,
                json.dumps(data)
            )
            return True
        except redis.RedisError:
            return False

    def get_cached_query(self, query: str) -> Optional[Any]:
        """
        Get and validate cached query result.

        SECURITY: Validates query cache data using Pydantic schema before
        returning result. Prevents injection of malformed results.

        Args:
            query: The query string (will be hashed)

        Returns:
            Cached query result if found and valid, None otherwise

        Raises:
            ConnectionError: If Redis is not connected
        """
        self._ensure_connected()
        query_hash = self._query_hash(query)
        key = f"{self.PREFIX_QUERY}{query_hash}"

        try:
            data = self._client.get(key)
            if data is None:
                return None

            # Parse JSON
            try:
                raw_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse query cache JSON for %s: %s",
                    query_hash,
                    e,
                    extra={"key": key, "query": log_safe_query(query)}
                )
                return None

            # Validate using Pydantic schema
            try:
                validated = QueryCacheModel(**raw_data)
                # Increment hit counter atomically
                updated_data = validated.model_dump()
                updated_data["hits"] = validated.hits + 1
                try:
                    self._client.setex(
                        key,
                        self.config.ttl_queries,
                        json.dumps(updated_data)
                    )
                except redis.RedisError as e:
                    logger.warning(
                        "Failed to update query cache hit counter: %s", e,
                        extra={"key": key}
                    )
                    # Continue anyway - hit counter is not critical
                return validated.result
            except ValidationError as e:
                logger.error(
                    "Query cache validation failed for %s: %s",
                    query_hash,
                    e,
                    extra={"key": key, "errors": e.errors(), "query": log_safe_query(query)}
                )
                return None

        except redis.RedisError as e:
            logger.error(
                "Redis error retrieving query cache %s: %s",
                query_hash,
                e,
                extra={"key": key}
            )
            return None

    # Embedding Cache

    def cache_embedding(
        self,
        text: str,
        embedding: List[float],
        model: str = "unknown",
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache an embedding vector.

        Args:
            text: The text that was embedded (used as cache key)
            embedding: The embedding vector
            model: Model name used for embedding
            ttl: TTL in seconds (default: 3600)

        Returns:
            True if cached successfully, False otherwise
        """
        self._ensure_connected()
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        key = f"{self.PREFIX_EMBEDDING}{text_hash}"

        # Store full model structure to match EmbeddingCacheModel schema
        data = {
            "query": text,
            "embedding": embedding,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            self._client.setex(
                key,
                ttl or 3600,  # Default 1 hour
                json.dumps(data)
            )
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to cache embedding: {e}")
            return False

    def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get and validate cached embedding.

        SECURITY: Validates embedding data using Pydantic schema before
        returning. Ensures embedding vector has expected format and size.

        Args:
            text: The text to get embedding for (will be hashed)

        Returns:
            Embedding vector if found and valid, None otherwise

        Raises:
            ConnectionError: If Redis is not connected
        """
        self._ensure_connected()
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        key = f"{self.PREFIX_EMBEDDING}{text_hash}"

        try:
            data = self._client.get(key)
            if data is None:
                return None

            # Parse JSON
            try:
                raw_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse embedding JSON for %s: %s",
                    text_hash,
                    e,
                    extra={"key": key}
                )
                return None

            # Validate using Pydantic schema
            try:
                # Raw JSON contains the full EmbeddingCacheModel structure
                validated = EmbeddingCacheModel(**raw_data)
                return validated.embedding
            except ValidationError as e:
                logger.error(
                    "Embedding validation failed for %s: %s",
                    text_hash,
                    e,
                    extra={"key": key, "errors": e.errors()}
                )
                return None

        except redis.RedisError as e:
            logger.error(
                "Redis error retrieving embedding %s: %s",
                text_hash,
                e,
                extra={"key": key}
            )
            return None

    def delete_cached_embedding(self, text: str) -> bool:
        """
        Delete a cached embedding.

        Args:
            text: The text whose embedding should be deleted

        Returns:
            True if deleted successfully, False otherwise
        """
        self._ensure_connected()
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        key = f"{self.PREFIX_EMBEDDING}{text_hash}"

        try:
            result = self._client.delete(key)
            return result > 0
        except redis.RedisError as e:
            logger.error(
                "Redis error deleting embedding %s: %s",
                text_hash,
                e,
                extra={"key": key}
            )
            return False

    # Context Window Management

    def push_context(self, session_id: str, message: Dict[str, Any], max_size: int = 100) -> bool:
        """Push a message to the context window."""
        self._ensure_connected()
        key = f"{self.PREFIX_CONTEXT}{session_id}"

        try:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._client.lpush(key, json.dumps(message))
            self._client.ltrim(key, 0, max_size - 1)
            self._client.expire(key, self.config.ttl_session)
            return True
        except redis.RedisError:
            return False

    def get_context(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get and validate recent context window messages.

        SECURITY: Validates each context message using Pydantic schema
        before returning. Skips invalid messages with logging.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of validated context messages (invalid ones filtered out)

        Raises:
            ConnectionError: If Redis is not connected
        """
        self._ensure_connected()
        key = f"{self.PREFIX_CONTEXT}{session_id}"

        try:
            messages = self._client.lrange(key, 0, limit - 1)
            validated_messages = []

            for i, message_json in enumerate(messages):
                try:
                    # Parse JSON
                    try:
                        raw_data = json.loads(message_json)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Failed to parse context message JSON at index %d "
                            "for session %s: %s",
                            i,
                            session_id,
                            e,
                            extra={"key": key}
                        )
                        continue

                    # Validate using Pydantic schema
                    try:
                        validated = ContextWindowItemModel(**raw_data)
                        validated_messages.append(validated.model_dump())
                    except ValidationError as e:
                        logger.warning(
                            "Context message validation failed at index %d "
                            "for session %s: %s",
                            i,
                            session_id,
                            e,
                            extra={
                                "key": key,
                                "errors": e.errors(),
                                "index": i
                            }
                        )
                        continue

                except Exception as e:
                    logger.error(
                        "Unexpected error processing context message at "
                        "index %d for session %s: %s",
                        i,
                        session_id,
                        e,
                        extra={"key": key, "index": i}
                    )
                    continue

            return validated_messages

        except redis.RedisError as e:
            logger.error(
                "Redis error retrieving context for %s: %s",
                session_id,
                e,
                extra={"key": key}
            )
            return []

    def clear_context(self, session_id: str) -> bool:
        """Clear context window for session."""
        self._ensure_connected()
        key = f"{self.PREFIX_CONTEXT}{session_id}"
        return self._client.delete(key) > 0

    # Utility Methods

    def flush_expired(self) -> int:
        """Redis handles TTL automatically, but this can force cleanup."""
        # Redis automatically removes expired keys
        # This method is here for interface consistency
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get Redis memory stats."""
        self._ensure_connected()

        try:
            info = self._client.info("memory")
            return {
                "used_memory": info.get("used_memory_human", "unknown"),
                "peak_memory": info.get("used_memory_peak_human", "unknown"),
                "connected": True
            }
        except redis.RedisError:
            return {"connected": False}

    def health_check(self) -> bool:
        """Check Redis health."""
        try:
            self._ensure_connected()
            return self._client.ping()
        except (redis.RedisError, ConnectionError):
            return False
