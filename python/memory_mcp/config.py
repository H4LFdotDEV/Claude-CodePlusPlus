# config.py
# Memory MCP Server Configuration
# Jeremiah Kroesche | Halfservers LLC

import os
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml
import logging

logger = logging.getLogger(__name__)

# Allowed configuration directories (security boundary)
_ALLOWED_CONFIG_DIRS = [
    os.path.expanduser("~/.claude-code-pp"),
    os.path.expanduser("~/.config/claude-code-pp"),
    "/etc/claude-code-pp",
]


def _validate_config_path(path: str) -> str:
    """
    Validate configuration file path to prevent path traversal attacks.

    SECURITY: Only allows loading config from designated config directories,
    the current working directory, or system temp directories (for testing).

    Args:
        path: Path to validate

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is outside allowed directories or invalid
    """
    import tempfile

    # Expand and resolve the path
    resolved = os.path.realpath(os.path.expanduser(path))

    # Check if path is within allowed directories
    for allowed_dir in _ALLOWED_CONFIG_DIRS:
        allowed_resolved = os.path.realpath(allowed_dir)
        if resolved.startswith(allowed_resolved + os.sep) or resolved == allowed_resolved:
            return resolved

    # Allow paths within the current working directory for development
    cwd = os.path.realpath(os.getcwd())
    if resolved.startswith(cwd + os.sep):
        return resolved

    # Allow paths within system temp directory (for testing)
    # SECURITY: This is acceptable because temp files are user-controlled
    # and the user is explicitly requesting to load them
    temp_dir = os.path.realpath(tempfile.gettempdir())
    if resolved.startswith(temp_dir + os.sep):
        return resolved

    raise ValueError(
        f"Config path '{path}' is outside allowed directories. "
        f"Allowed: {_ALLOWED_CONFIG_DIRS}"
    )


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_session: int = 3600  # 1 hour
    ttl_templates: int = 86400  # 24 hours
    ttl_queries: int = 3600  # 1 hour (increased from 5 min for better cache hit ratio)


@dataclass
class SQLiteConfig:
    path: str = "~/.claude-code-pp/memory/metadata.db"


@dataclass
class VaultConfig:
    path: str = "~/.claude-code-pp/memory/vault"
    obsidian_compatible: bool = True


@dataclass
class EmbeddingConfig:
    provider: str = "local"  # local, openai, voyage, custom
    local_model: str = "nomic-embed-text"
    local_endpoint: str = "http://localhost:11434"
    openai_model: str = "text-embedding-3-small"
    voyage_model: str = "voyage-code-2"
    custom_endpoint: Optional[str] = None
    fallback_order: list = field(default_factory=lambda: ["local", "openai"])


@dataclass
class GraphitiConfig:
    """Configuration for Graphiti/Neo4j knowledge graph (warm tier)."""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: Optional[str] = None  # From NEO4J_PASSWORD env var
    openai_api_key: Optional[str] = None  # For entity extraction
    enabled: bool = True  # Set to False to disable Graphiti


@dataclass
class LivegrepConfig:
    """Configuration for livegrep code search (cold tier)."""
    endpoint: str = "http://localhost:8910"
    backend_port: int = 9999  # gRPC port for codesearch
    index_path: str = "~/.claude-code-pp/livegrep/index.idx"
    repos_path: str = "~/.claude-code-pp/livegrep/repos"
    enabled: bool = True  # Set to False to disable livegrep


@dataclass
class MemoryConfig:
    redis: RedisConfig = field(default_factory=RedisConfig)
    sqlite: SQLiteConfig = field(default_factory=SQLiteConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    graphiti: GraphitiConfig = field(default_factory=GraphitiConfig)
    livegrep: LivegrepConfig = field(default_factory=LivegrepConfig)

    # Paths
    base_path: str = "~/.claude-code-pp"

    @classmethod
    def from_yaml(cls, path: str) -> "MemoryConfig":
        """
        Load configuration from YAML file.

        SECURITY: Validates path to prevent traversal attacks.
        """
        try:
            validated_path = _validate_config_path(path)
        except ValueError as e:
            logger.warning(f"Config path validation failed: {e}. Using defaults.")
            return cls()

        if not os.path.exists(validated_path):
            return cls()

        with open(validated_path) as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        # Parse memory section
        memory = data.get("memory", {})

        # Redis config
        redis_data = memory.get("redis", {})
        config.redis = RedisConfig(
            host=redis_data.get("host", "localhost"),
            port=redis_data.get("port", 6379),
            db=redis_data.get("db", 0),
            password=redis_data.get("password"),
            ttl_session=redis_data.get("ttl_session", 3600),
            ttl_templates=redis_data.get("ttl_templates", 86400),
            ttl_queries=redis_data.get("ttl_queries", 3600),
        )

        # Paths
        paths = memory.get("paths", {})
        config.vault.path = paths.get("vault", config.vault.path)
        config.sqlite.path = paths.get("database", config.sqlite.path)

        # Embedding config
        embedding = data.get("embeddings", {})
        config.embedding.provider = embedding.get("provider", "local")

        providers = embedding.get("providers", {})
        if "local" in providers:
            config.embedding.local_model = providers["local"].get("model", config.embedding.local_model)
            config.embedding.local_endpoint = providers["local"].get("endpoint", config.embedding.local_endpoint)

        # Graphiti config (knowledge graph - warm tier)
        graphiti_data = memory.get("graphiti", {})
        config.graphiti = GraphitiConfig(
            uri=graphiti_data.get("uri", os.environ.get("NEO4J_URI", "bolt://localhost:7687")),
            user=graphiti_data.get("user", os.environ.get("NEO4J_USER", "neo4j")),
            password=graphiti_data.get("password", os.environ.get("NEO4J_PASSWORD")),
            openai_api_key=graphiti_data.get("openai_api_key", os.environ.get("OPENAI_API_KEY")),
            enabled=graphiti_data.get("enabled", True),
        )

        # livegrep config (code search - cold tier)
        livegrep_data = memory.get("livegrep", {})
        config.livegrep = LivegrepConfig(
            endpoint=livegrep_data.get("endpoint", os.environ.get("LIVEGREP_ENDPOINT", "http://localhost:8910")),
            backend_port=livegrep_data.get("backend_port", 9999),
            index_path=livegrep_data.get("index_path", "~/.claude-code-pp/livegrep/index.idx"),
            repos_path=livegrep_data.get("repos_path", "~/.claude-code-pp/livegrep/repos"),
            enabled=livegrep_data.get("enabled", True),
        )

        return config

    def expand_paths(self):
        """Expand all ~ in paths."""
        self.base_path = os.path.expanduser(self.base_path)
        self.sqlite.path = os.path.expanduser(self.sqlite.path)
        self.vault.path = os.path.expanduser(self.vault.path)
        self.livegrep.index_path = os.path.expanduser(self.livegrep.index_path)
        self.livegrep.repos_path = os.path.expanduser(self.livegrep.repos_path)

    def ensure_directories(self):
        """Create necessary directories."""
        self.expand_paths()
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        Path(self.vault.path).mkdir(parents=True, exist_ok=True)
        Path(self.sqlite.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.livegrep.index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.livegrep.repos_path).mkdir(parents=True, exist_ok=True)


# Global config instance with thread-safe initialization
_config: Optional[MemoryConfig] = None
_config_lock = threading.Lock()


def get_config() -> MemoryConfig:
    """Get or create global config with thread-safe double-checked locking."""
    global _config
    # First check without lock (fast path)
    if _config is None:
        with _config_lock:
            # Second check with lock (thread-safe initialization)
            if _config is None:
                config_path = os.environ.get(
                    "CLAUDE_CODE_PP_CONFIG",
                    "~/.claude-code-pp/config/settings.yaml"
                )
                _config = MemoryConfig.from_yaml(config_path)
                _config.ensure_directories()
    return _config


def set_config(config: MemoryConfig):
    """Set global config (thread-safe)."""
    global _config
    with _config_lock:
        _config = config
