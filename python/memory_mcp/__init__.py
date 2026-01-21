# Memory MCP Server for Claude Code++
# Jeremiah Kroesche | Halfservers LLC
#
# Tiered memory system: Redis (hot) → FAISS (warm) → SQLite/Markdown (cold)

__version__ = "1.0.0"
__author__ = "Jeremiah Kroesche"

from .config import MemoryConfig, get_config, set_config
from .sqlite_index import SQLiteIndex, MemoryDocument
from .vault_manager import VaultManager, VaultNote
from .server import MemoryMCPServer

# Optional imports (may not be available)
try:
    from .redis_client import RedisClient, SessionState
except ImportError:
    RedisClient = None
    SessionState = None

try:
    from .faiss_manager import FAISSManager, SearchResult
except ImportError:
    FAISSManager = None
    SearchResult = None

try:
    from .embedding_provider import (
        EmbeddingProvider,
        LocalEmbeddingProvider,
        OpenAIEmbeddingProvider,
        VoyageEmbeddingProvider,
        FallbackEmbeddingProvider,
        get_embedding_provider
    )
except ImportError:
    EmbeddingProvider = None
    get_embedding_provider = None

__all__ = [
    # Core
    "MemoryConfig",
    "get_config",
    "set_config",
    "SQLiteIndex",
    "MemoryDocument",
    "VaultManager",
    "VaultNote",
    "MemoryMCPServer",
    # Optional
    "RedisClient",
    "SessionState",
    "FAISSManager",
    "SearchResult",
    "EmbeddingProvider",
    "get_embedding_provider",
]
