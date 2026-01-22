# config.py
# Memory MCP Server Configuration
# Jeremiah Kroesche | Halfservers LLC

import os
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml


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
class FAISSConfig:
    index_type: str = "flat"  # flat, ivf, hnsw
    dimension: int = 768  # nomic-embed-text default
    nlist: int = 100  # for IVF
    nprobe: int = 10  # for IVF
    rebuild_threshold: float = 0.1  # rebuild when 10% deleted


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
class MemoryConfig:
    redis: RedisConfig = field(default_factory=RedisConfig)
    faiss: FAISSConfig = field(default_factory=FAISSConfig)
    sqlite: SQLiteConfig = field(default_factory=SQLiteConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    # Paths
    base_path: str = "~/.claude-code-pp"
    faiss_path: str = "~/.claude-code-pp/memory/faiss"

    @classmethod
    def from_yaml(cls, path: str) -> "MemoryConfig":
        """Load configuration from YAML file."""
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return cls()

        with open(path) as f:
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

        # FAISS config
        faiss_data = memory.get("faiss", {})
        config.faiss = FAISSConfig(
            index_type=faiss_data.get("index_type", "flat"),
            rebuild_threshold=faiss_data.get("rebuild_threshold", 0.1),
        )

        # Paths
        paths = memory.get("paths", {})
        config.vault.path = paths.get("vault", config.vault.path)
        config.faiss_path = paths.get("faiss", config.faiss_path)
        config.sqlite.path = paths.get("database", config.sqlite.path)

        # Embedding config
        embedding = data.get("embeddings", {})
        config.embedding.provider = embedding.get("provider", "local")

        providers = embedding.get("providers", {})
        if "local" in providers:
            config.embedding.local_model = providers["local"].get("model", config.embedding.local_model)
            config.embedding.local_endpoint = providers["local"].get("endpoint", config.embedding.local_endpoint)

        return config

    def expand_paths(self):
        """Expand all ~ in paths."""
        self.base_path = os.path.expanduser(self.base_path)
        self.faiss_path = os.path.expanduser(self.faiss_path)
        self.sqlite.path = os.path.expanduser(self.sqlite.path)
        self.vault.path = os.path.expanduser(self.vault.path)

    def ensure_directories(self):
        """Create necessary directories."""
        self.expand_paths()
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        Path(self.faiss_path).mkdir(parents=True, exist_ok=True)
        Path(self.vault.path).mkdir(parents=True, exist_ok=True)
        Path(self.sqlite.path).parent.mkdir(parents=True, exist_ok=True)


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
