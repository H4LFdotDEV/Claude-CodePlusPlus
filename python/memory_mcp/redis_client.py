# redis_client.py
# Redis Client for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Hot memory layer - session state, recent queries, templates

import json
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .config import get_config, RedisConfig


@dataclass
class SessionState:
    """Current session state stored in Redis."""
    session_id: str
    project_path: str
    active_files: List[str]
    recent_queries: List[str]
    context_window: List[Dict[str, Any]]
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        return cls(**data)


@dataclass
class CachedQuery:
    """Cached query result."""
    query: str
    result: Any
    embedding: Optional[List[float]]
    created_at: str
    hits: int = 0


class RedisClient:
    """Redis client for hot memory layer."""

    # Key prefixes
    PREFIX_SESSION = "cc:session:"
    PREFIX_TEMPLATE = "cc:template:"
    PREFIX_QUERY = "cc:query:"
    PREFIX_EMBEDDING = "cc:embed:"
    PREFIX_CONTEXT = "cc:context:"

    def __init__(self, config: Optional[RedisConfig] = None):
        if not REDIS_AVAILABLE:
            raise ImportError("redis is not installed. Run: pip install redis")

        self.config = config or get_config().redis
        self._client: Optional[redis.Redis] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self._client.ping()
            self._connected = True
            return True
        except redis.ConnectionError:
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            self._client.close()
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
        """Retrieve session state."""
        self._ensure_connected()
        key = f"{self.PREFIX_SESSION}{session_id}"

        try:
            data = self._client.get(key)
            if data:
                return SessionState.from_dict(json.loads(data))
            return None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete session state."""
        self._ensure_connected()
        key = f"{self.PREFIX_SESSION}{session_id}"
        return self._client.delete(key) > 0

    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        self._ensure_connected()
        pattern = f"{self.PREFIX_SESSION}*"
        keys = self._client.keys(pattern)
        return [k.replace(self.PREFIX_SESSION, "") for k in keys]

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
        """Get cached template content."""
        self._ensure_connected()
        key = f"{self.PREFIX_TEMPLATE}{name}"

        try:
            data = self._client.get(key)
            if data:
                return json.loads(data).get("content")
            return None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    def list_templates(self) -> List[str]:
        """List all cached template names."""
        self._ensure_connected()
        pattern = f"{self.PREFIX_TEMPLATE}*"
        keys = self._client.keys(pattern)
        return [k.replace(self.PREFIX_TEMPLATE, "") for k in keys]

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
        """Get cached query result."""
        self._ensure_connected()
        query_hash = self._query_hash(query)
        key = f"{self.PREFIX_QUERY}{query_hash}"

        try:
            data = self._client.get(key)
            if data:
                parsed = json.loads(data)
                # Increment hit counter
                parsed["hits"] = parsed.get("hits", 0) + 1
                self._client.setex(
                    key,
                    self.config.ttl_queries,
                    json.dumps(parsed)
                )
                return parsed.get("result")
            return None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    # Embedding Cache

    def cache_embedding(self, text: str, embedding: List[float], ttl: Optional[int] = None) -> bool:
        """Cache an embedding."""
        self._ensure_connected()
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        key = f"{self.PREFIX_EMBEDDING}{text_hash}"

        try:
            self._client.setex(
                key,
                ttl or 3600,  # Default 1 hour
                json.dumps(embedding)
            )
            return True
        except redis.RedisError:
            return False

    def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding."""
        self._ensure_connected()
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        key = f"{self.PREFIX_EMBEDDING}{text_hash}"

        try:
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except (redis.RedisError, json.JSONDecodeError):
            return None

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

    def get_context(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent context window messages."""
        self._ensure_connected()
        key = f"{self.PREFIX_CONTEXT}{session_id}"

        try:
            messages = self._client.lrange(key, 0, limit - 1)
            return [json.loads(m) for m in messages]
        except (redis.RedisError, json.JSONDecodeError):
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
