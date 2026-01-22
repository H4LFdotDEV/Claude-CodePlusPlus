# Memory MCP Server for Claude Code++
# Jeremiah Kroesche | Halfservers LLC
#
# Tiered memory system:
#   Hot:     Redis (session cache)
#   Warm:    Graphiti/Neo4j (knowledge graph)
#   Cold:    livegrep (artifact search)
#   Archive: Obsidian vault (human-readable export)
#
# SQLite stores metadata only (timestamps, tags, indexes)

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
    from .graphiti_manager import GraphitiManager
except ImportError:
    GraphitiManager = None

try:
    from .livegrep_client import LivegrepClient
except ImportError:
    LivegrepClient = None

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
    # Optional - Tiers
    "RedisClient",
    "SessionState",
    "GraphitiManager",
    "LivegrepClient",
    # Optional - Embeddings
    "EmbeddingProvider",
    "get_embedding_provider",
]
