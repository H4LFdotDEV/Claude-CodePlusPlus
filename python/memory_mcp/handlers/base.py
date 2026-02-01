# handlers/base.py
# Base handler class with shared dependencies
# All tool handlers inherit from this

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..sqlite_index import SQLiteIndex
    from ..vault_manager import VaultManager
    from ..redis_client import RedisClient
    from ..embedding_provider import FallbackEmbeddingProvider
    from ..tier_manager import TierManager

logger = logging.getLogger("memory_mcp")


class BaseHandler:
    """Base class for all tool handlers.

    Provides shared access to:
    - sqlite: Cold tier storage (SQLite FTS)
    - vault: Archive tier (Obsidian-compatible markdown)
    - redis: Hot tier cache (optional)
    - embedder: Embedding provider (optional)
    - tier_manager: Multi-tier orchestrator (optional)
    - session_id: Current session identifier
    """

    def __init__(
        self,
        sqlite: "SQLiteIndex",
        vault: "VaultManager",
        redis: Optional["RedisClient"] = None,
        embedder: Optional["FallbackEmbeddingProvider"] = None,
        tier_manager: Optional["TierManager"] = None,
        session_id: str = ""
    ):
        self.sqlite = sqlite
        self.vault = vault
        self.redis = redis
        self.embedder = embedder
        self.tier_manager = tier_manager
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        """Set session ID."""
        self._session_id = value
