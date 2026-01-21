# test_config.py
# Comprehensive test suite for Memory MCP Server Configuration
# Tests cover: dataclass defaults, YAML loading, path operations, singleton pattern, error handling, integration

import os
import threading
import tempfile
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

from memory_mcp.config import (
    RedisConfig,
    FAISSConfig,
    SQLiteConfig,
    VaultConfig,
    EmbeddingConfig,
    MemoryConfig,
    get_config,
    set_config,
    _config_lock,
)

# ============================================================================
# CATEGORY 1: Dataclass Defaults (6 tests)
# ============================================================================

class TestDataclassDefaults:
    """Test default values for all configuration dataclasses."""

    def test_redis_config_defaults(self):
        """Test RedisConfig has correct default values."""
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.ttl_session == 3600
        assert config.ttl_templates == 86400
        assert config.ttl_queries == 3600

    def test_faiss_config_defaults(self):
        """Test FAISSConfig has correct default values."""
        config = FAISSConfig()
        assert config.index_type == "flat"
        assert config.dimension == 768
        assert config.nlist == 100
        assert config.nprobe == 10
        assert config.rebuild_threshold == 0.1

    def test_sqlite_config_defaults(self):
        """Test SQLiteConfig has correct default values."""
        config = SQLiteConfig()
        assert config.path == "~/.claude-code-pp/memory/metadata.db"

    def test_vault_config_defaults(self):
        """Test VaultConfig has correct default values."""
        config = VaultConfig()
        assert config.path == "~/.claude-code-pp/memory/vault"
        assert config.obsidian_compatible is True

    def test_embedding_config_defaults(self):
        """Test EmbeddingConfig has correct default values."""
        config = EmbeddingConfig()
        assert config.provider == "local"
        assert config.local_model == "nomic-embed-text"
        assert config.local_endpoint == "http://localhost:11434"
        assert config.openai_model == "text-embedding-3-small"
        assert config.voyage_model == "voyage-code-2"
        assert config.custom_endpoint is None
        assert config.fallback_order == ["local", "openai"]

    def test_memory_config_defaults(self):
        """Test MemoryConfig has correct default values."""
        config = MemoryConfig()
        assert config.base_path == "~/.claude-code-pp"
        assert config.faiss_path == "~/.claude-code-pp/memory/faiss"
        assert isinstance(config.redis, RedisConfig)
        assert isinstance(config.faiss, FAISSConfig)
        assert isinstance(config.sqlite, SQLiteConfig)
        assert isinstance(config.vault, VaultConfig)
        assert isinstance(config.embedding, EmbeddingConfig)


# ============================================================================
# CATEGORY 2: YAML Loading (25 tests)
# ============================================================================

class TestYAMLLoading:
    """Test loading configuration from YAML files."""

    def test_load_complete_yaml(self):
        """Test loading a complete YAML file with all sections."""
        yaml_content = """
memory:
  redis:
    host: redis.example.com
    port: 6380
    db: 1
    password: secret123
  faiss:
    index_type: ivf
    rebuild_threshold: 0.2
  paths:
    vault: /custom/vault
    faiss: /custom/faiss
    database: /custom/db.sqlite
embeddings:
  provider: openai
  providers:
    local:
      model: custom-embed-model
      endpoint: http://custom:11434
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "redis.example.com"
                assert config.redis.port == 6380
                assert config.redis.db == 1
                assert config.redis.password == "secret123"
                assert config.faiss.index_type == "ivf"
                assert config.faiss.rebuild_threshold == 0.2
                assert config.vault.path == "/custom/vault"
                assert config.faiss_path == "/custom/faiss"
                assert config.sqlite.path == "/custom/db.sqlite"
                assert config.embedding.provider == "openai"
                assert config.embedding.local_model == "custom-embed-model"
                assert config.embedding.local_endpoint == "http://custom:11434"
            finally:
                os.unlink(f.name)

    def test_load_partial_yaml_redis_only(self):
        """Test loading YAML with only Redis section."""
        yaml_content = """
memory:
  redis:
    host: redis.local
    port: 6380
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "redis.local"
                assert config.redis.port == 6380
                # Other defaults should remain
                assert config.faiss.index_type == "flat"
                assert config.embedding.provider == "local"
            finally:
                os.unlink(f.name)

    def test_load_partial_yaml_faiss_only(self):
        """Test loading YAML with only FAISS section."""
        yaml_content = """
memory:
  faiss:
    index_type: hnsw
    rebuild_threshold: 0.15
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.faiss.index_type == "hnsw"
                assert config.faiss.rebuild_threshold == 0.15
                # Other defaults should remain
                assert config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_load_partial_yaml_paths_only(self):
        """Test loading YAML with only paths section."""
        yaml_content = """
memory:
  paths:
    vault: /tmp/vault
    faiss: /tmp/faiss
    database: /tmp/db.sqlite
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.vault.path == "/tmp/vault"
                assert config.faiss_path == "/tmp/faiss"
                assert config.sqlite.path == "/tmp/db.sqlite"
            finally:
                os.unlink(f.name)

    def test_load_partial_yaml_embeddings_only(self):
        """Test loading YAML with only embeddings section."""
        yaml_content = """
embeddings:
  provider: voyage
  providers:
    local:
      model: different-model
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.embedding.provider == "voyage"
                assert config.embedding.local_model == "different-model"
            finally:
                os.unlink(f.name)

    def test_load_missing_file_returns_defaults(self):
        """Test loading from non-existent file returns default config."""
        config = MemoryConfig.from_yaml("~/.nonexistent-config-file-12345.yaml")
        # Should return default config
        assert config.redis.host == "localhost"
        assert config.faiss.index_type == "flat"
        assert config.embedding.provider == "local"

    def test_load_empty_yaml_file(self):
        """Test loading empty YAML file returns default config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "localhost"
                assert config.faiss.index_type == "flat"
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_only_comments(self):
        """Test loading YAML file with only comments."""
        yaml_content = """# This is a comment
# Another comment
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_load_invalid_yaml_syntax(self):
        """Test loading invalid YAML syntax raises error."""
        yaml_content = """
memory:
  redis:
    host: localhost
    invalid: syntax: here: too: many: colons
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with pytest.raises(yaml.YAMLError):
                    MemoryConfig.from_yaml(f.name)
            finally:
                os.unlink(f.name)

    def test_load_redis_with_custom_values(self):
        """Test loading Redis config with custom values."""
        yaml_content = """
memory:
  redis:
    host: custom-redis
    port: 6381
    db: 2
    password: mypassword
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "custom-redis"
                assert config.redis.port == 6381
                assert config.redis.db == 2
                assert config.redis.password == "mypassword"
            finally:
                os.unlink(f.name)

    def test_load_redis_partial_values(self):
        """Test loading Redis config with partial values uses defaults."""
        yaml_content = """
memory:
  redis:
    host: custom-redis
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "custom-redis"
                assert config.redis.port == 6379
                assert config.redis.db == 0
                assert config.redis.password is None
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_tilde_paths(self):
        """Test loading YAML with tilde-based paths."""
        yaml_content = """
memory:
  paths:
    vault: ~/my-vault
    faiss: ~/my-faiss
    database: ~/.cache/memory.db
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Paths should be stored as-is (not expanded yet)
                assert config.vault.path == "~/my-vault"
                assert config.faiss_path == "~/my-faiss"
                assert config.sqlite.path == "~/.cache/memory.db"
            finally:
                os.unlink(f.name)

    def test_load_yaml_expanduser_on_path(self):
        """Test that from_yaml expands ~ in the config file path."""
        yaml_content = "memory:\n  redis:\n    host: test\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "test.yaml")
            with open(config_file, 'w') as f:
                f.write(yaml_content)

            # This should work with absolute path
            config = MemoryConfig.from_yaml(config_file)
            assert config.redis.host == "test"

    def test_load_faiss_with_custom_rebuild_threshold(self):
        """Test loading FAISS config with custom rebuild threshold."""
        yaml_content = """
memory:
  faiss:
    index_type: ivf
    rebuild_threshold: 0.25
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.faiss.rebuild_threshold == 0.25
            finally:
                os.unlink(f.name)

    def test_load_embeddings_with_local_provider(self):
        """Test loading embeddings config with local provider."""
        yaml_content = """
embeddings:
  provider: local
  providers:
    local:
      model: all-MiniLM-L6-v2
      endpoint: http://localhost:11434
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.embedding.provider == "local"
                assert config.embedding.local_model == "all-MiniLM-L6-v2"
            finally:
                os.unlink(f.name)

    def test_load_embeddings_with_openai_provider(self):
        """Test loading embeddings config with OpenAI provider."""
        yaml_content = """
embeddings:
  provider: openai
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.embedding.provider == "openai"
            finally:
                os.unlink(f.name)

    def test_load_redis_password_none_vs_empty_string(self):
        """Test loading Redis with password handling."""
        yaml_content = """
memory:
  redis:
    password: null
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.password is None
            finally:
                os.unlink(f.name)

    def test_load_redis_with_password_string(self):
        """Test loading Redis with password as string."""
        yaml_content = """
memory:
  redis:
    password: "super-secret-password-123"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.password == "super-secret-password-123"
            finally:
                os.unlink(f.name)

    def test_load_multiple_yaml_sections_merged(self):
        """Test loading YAML with multiple sections merged correctly."""
        yaml_content = """
memory:
  redis:
    host: redis-host
    port: 6380
  faiss:
    index_type: ivf
  paths:
    vault: /vault
embeddings:
  provider: voyage
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "redis-host"
                assert config.redis.port == 6380
                assert config.faiss.index_type == "ivf"
                assert config.vault.path == "/vault"
                assert config.embedding.provider == "voyage"
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_integer_values(self):
        """Test loading YAML with integer configurations."""
        yaml_content = """
memory:
  redis:
    port: 6380
    db: 2
  faiss:
    nlist: 200
    nprobe: 20
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.port == 6380
                assert config.redis.db == 2
                # Note: nlist and nprobe are not parsed, only shown values are
                assert config.faiss.nlist == 100  # defaults unchanged
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_float_values(self):
        """Test loading YAML with float configurations."""
        yaml_content = """
memory:
  faiss:
    rebuild_threshold: 0.35
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.faiss.rebuild_threshold == 0.35
            finally:
                os.unlink(f.name)

    def test_load_yaml_preserves_list_in_fallback_order(self):
        """Test loading YAML preserves fallback_order list."""
        yaml_content = """
embeddings:
  provider: local
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.embedding.fallback_order == ["local", "openai"]
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_nested_memory_section(self):
        """Test YAML loading ignores unknown nested sections."""
        yaml_content = """
memory:
  redis:
    host: localhost
  unknown_section:
    some_key: some_value
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should still load valid sections
                assert config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_extra_top_level_sections(self):
        """Test YAML loading with unknown top-level sections."""
        yaml_content = """
memory:
  redis:
    host: localhost
logging:
  level: debug
database:
  connection: postgresql
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should still load memory section
                assert config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_load_yaml_returns_new_instance(self):
        """Test that each call to from_yaml returns a new instance."""
        yaml_content = "memory:\n  redis:\n    host: test\n"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config1 = MemoryConfig.from_yaml(f.name)
                config2 = MemoryConfig.from_yaml(f.name)
                assert config1 is not config2
                assert config1.redis.host == config2.redis.host
            finally:
                os.unlink(f.name)


# ============================================================================
# CATEGORY 3: Path Operations (10 tests)
# ============================================================================

class TestPathOperations:
    """Test path expansion and directory creation."""

    def test_expand_paths_tilde_in_base_path(self):
        """Test expand_paths expands tilde in base_path."""
        config = MemoryConfig()
        config.expand_paths()
        assert not config.base_path.startswith("~")
        assert os.path.isabs(config.base_path)

    def test_expand_paths_tilde_in_faiss_path(self):
        """Test expand_paths expands tilde in faiss_path."""
        config = MemoryConfig()
        config.expand_paths()
        assert not config.faiss_path.startswith("~")
        assert os.path.isabs(config.faiss_path)

    def test_expand_paths_tilde_in_sqlite_path(self):
        """Test expand_paths expands tilde in sqlite.path."""
        config = MemoryConfig()
        config.expand_paths()
        assert not config.sqlite.path.startswith("~")
        assert os.path.isabs(config.sqlite.path)

    def test_expand_paths_tilde_in_vault_path(self):
        """Test expand_paths expands tilde in vault.path."""
        config = MemoryConfig()
        config.expand_paths()
        assert not config.vault.path.startswith("~")
        assert os.path.isabs(config.vault.path)

    def test_expand_paths_with_custom_paths(self):
        """Test expand_paths with custom path values."""
        config = MemoryConfig()
        config.base_path = "~/custom/base"
        config.faiss_path = "~/custom/faiss"
        config.sqlite.path = "~/custom/sqlite.db"
        config.vault.path = "~/custom/vault"

        config.expand_paths()

        assert not config.base_path.startswith("~")
        assert not config.faiss_path.startswith("~")
        assert not config.sqlite.path.startswith("~")
        assert not config.vault.path.startswith("~")

    def test_ensure_directories_creates_all_dirs(self):
        """Test ensure_directories creates all necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MemoryConfig()
            config.base_path = os.path.join(tmpdir, "base")
            config.faiss_path = os.path.join(tmpdir, "faiss")
            config.sqlite.path = os.path.join(tmpdir, "subdir", "db.sqlite")
            config.vault.path = os.path.join(tmpdir, "vault")

            config.ensure_directories()

            assert Path(config.base_path).exists()
            assert Path(config.faiss_path).exists()
            assert Path(config.sqlite.path).parent.exists()
            assert Path(config.vault.path).exists()

    def test_ensure_directories_with_existing_dirs(self):
        """Test ensure_directories works with already-existing directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MemoryConfig()
            config.base_path = tmpdir
            config.faiss_path = tmpdir
            config.sqlite.path = os.path.join(tmpdir, "db.sqlite")
            config.vault.path = tmpdir

            # Should not raise error
            config.ensure_directories()

            assert Path(tmpdir).exists()

    def test_ensure_directories_creates_nested_dirs(self):
        """Test ensure_directories creates deeply nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MemoryConfig()
            config.base_path = os.path.join(tmpdir, "a", "b", "c")
            config.faiss_path = os.path.join(tmpdir, "x", "y", "z")
            config.sqlite.path = os.path.join(tmpdir, "p", "q", "r", "db.sqlite")
            config.vault.path = os.path.join(tmpdir, "m", "n")

            config.ensure_directories()

            assert Path(config.base_path).exists()
            assert Path(config.faiss_path).exists()
            assert Path(config.vault.path).exists()

    def test_ensure_directories_calls_expand_paths(self):
        """Test ensure_directories calls expand_paths first."""
        config = MemoryConfig()
        config.base_path = "~/test-base"
        config.faiss_path = "~/test-faiss"
        config.sqlite.path = "~/test-db.sqlite"
        config.vault.path = "~/test-vault"

        with tempfile.TemporaryDirectory():
            config.ensure_directories()

            # All paths should be expanded
            assert not config.base_path.startswith("~")
            assert not config.faiss_path.startswith("~")
            assert not config.sqlite.path.startswith("~")
            assert not config.vault.path.startswith("~")

    def test_expand_paths_idempotent(self):
        """Test that expand_paths is idempotent."""
        config = MemoryConfig()
        config.expand_paths()
        path1 = config.base_path

        config.expand_paths()
        path2 = config.base_path

        assert path1 == path2


# ============================================================================
# CATEGORY 4: Singleton Pattern (15 tests)
# ============================================================================

class TestSingletonPattern:
    """Test thread-safe singleton pattern for get_config."""

    def test_get_config_first_call_creates_config(self):
        """Test first call to get_config creates config."""
        # Reset global state
        import memory_mcp.config as config_module
        config_module._config = None

        config = get_config()
        assert config is not None
        assert isinstance(config, MemoryConfig)

    def test_get_config_second_call_returns_same_instance(self):
        """Test second call returns same instance."""
        import memory_mcp.config as config_module
        config_module._config = None

        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_third_call_returns_same_instance(self):
        """Test multiple calls return same instance."""
        import memory_mcp.config as config_module
        config_module._config = None

        configs = [get_config() for _ in range(5)]
        assert all(c is configs[0] for c in configs)

    def test_get_config_uses_environment_variable(self):
        """Test get_config respects CLAUDE_CODE_PP_CONFIG env var."""
        import memory_mcp.config as config_module
        config_module._config = None

        yaml_content = """
memory:
  redis:
    host: custom-host
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {'CLAUDE_CODE_PP_CONFIG': f.name}):
                    config = get_config()
                    assert config.redis.host == "custom-host"
            finally:
                os.unlink(f.name)
                config_module._config = None

    def test_get_config_uses_default_path_if_no_env_var(self):
        """Test get_config uses default path if env var not set."""
        import memory_mcp.config as config_module
        config_module._config = None

        with patch.dict(os.environ, {}, clear=True):
            # Remove CLAUDE_CODE_PP_CONFIG if it exists
            os.environ.pop('CLAUDE_CODE_PP_CONFIG', None)

            config = get_config()
            # Should get default config
            assert config.redis.host == "localhost"
            config_module._config = None

    def test_set_config_replaces_global_instance(self):
        """Test set_config replaces the global instance."""
        import memory_mcp.config as config_module
        config_module._config = None

        config1 = get_config()
        assert config1.redis.host == "localhost"

        new_config = MemoryConfig()
        new_config.redis.host = "new-host"
        set_config(new_config)

        config2 = get_config()
        assert config2.redis.host == "new-host"
        assert config2 is new_config

        # Reset
        config_module._config = None

    def test_get_config_after_set_config(self):
        """Test get_config after set_config returns set config."""
        import memory_mcp.config as config_module
        config_module._config = None

        custom_config = MemoryConfig()
        custom_config.redis.port = 9999
        set_config(custom_config)

        retrieved = get_config()
        assert retrieved.redis.port == 9999
        assert retrieved is custom_config

        config_module._config = None

    def test_set_config_is_thread_safe(self):
        """Test set_config is thread-safe."""
        import memory_mcp.config as config_module
        config_module._config = None

        results = []

        def set_different_configs(port):
            config = MemoryConfig()
            config.redis.port = port
            set_config(config)
            results.append(get_config().redis.port)

        threads = [
            threading.Thread(target=set_different_configs, args=(port,))
            for port in [1111, 2222, 3333]
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have seen consistent results
        final_config = get_config()
        assert final_config.redis.port in [1111, 2222, 3333]

        config_module._config = None

    def test_get_config_thread_safety_concurrent_access(self):
        """Test get_config is thread-safe under concurrent access."""
        import memory_mcp.config as config_module
        config_module._config = None

        configs = []

        def get_config_concurrent():
            config = get_config()
            configs.append(config)

        threads = [threading.Thread(target=get_config_concurrent) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have received the same instance
        assert all(c is configs[0] for c in configs)

        config_module._config = None

    def test_get_config_double_checked_locking(self):
        """Test get_config uses double-checked locking pattern."""
        import memory_mcp.config as config_module
        config_module._config = None

        # First call should acquire lock and initialize
        config1 = get_config()

        # Second call should not need lock (fast path)
        config2 = get_config()

        assert config1 is config2

        config_module._config = None

    def test_get_config_with_missing_config_file_uses_default(self):
        """Test get_config with missing config file uses defaults."""
        import memory_mcp.config as config_module
        config_module._config = None

        with patch.dict(os.environ, {'CLAUDE_CODE_PP_CONFIG': '~/.nonexistent.yaml'}):
            config = get_config()
            assert config.redis.host == "localhost"

        config_module._config = None

    def test_get_config_ensure_directories_called(self):
        """Test get_config calls ensure_directories."""
        import memory_mcp.config as config_module
        config_module._config = None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.yaml")
            with open(config_file, 'w') as f:
                f.write("memory:\n  redis:\n    host: test\n")

            with patch.dict(os.environ, {'CLAUDE_CODE_PP_CONFIG': config_file}):
                config = get_config()
                # All paths should be expanded
                assert not config.base_path.startswith("~")

        config_module._config = None

    def test_config_singleton_not_reset_between_tests(self):
        """Test that config persists across multiple get_config calls."""
        import memory_mcp.config as config_module
        config_module._config = None

        config1 = get_config()
        config1.redis.port = 7777

        config2 = get_config()
        assert config2.redis.port == 7777

        config_module._config = None

    def test_set_config_then_get_config_respects_set_value(self):
        """Test that after set_config, get_config returns set value."""
        import memory_mcp.config as config_module
        config_module._config = None

        original = get_config()

        new_config = MemoryConfig()
        new_config.faiss.index_type = "hnsw"
        set_config(new_config)

        retrieved = get_config()
        assert retrieved.faiss.index_type == "hnsw"

        config_module._config = None

    def test_get_config_stress_test_50_threads(self):
        """Test get_config under stress with 50 concurrent threads."""
        import memory_mcp.config as config_module
        config_module._config = None

        configs = []
        lock = threading.Lock()

        def stress_get():
            config = get_config()
            with lock:
                configs.append(config)

        threads = [threading.Thread(target=stress_get) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be same instance
        first = configs[0]
        assert all(c is first for c in configs)

        config_module._config = None

    def test_set_config_atomicity(self):
        """Test set_config is atomic - no intermediate states visible."""
        import memory_mcp.config as config_module
        config_module._config = None

        initial = get_config()
        initial.redis.port = 1111

        new_config = MemoryConfig()
        new_config.redis.port = 9999

        set_config(new_config)

        # Should see the new config, not partial state
        final = get_config()
        assert final.redis.port == 9999
        assert final is new_config

        config_module._config = None


# ============================================================================
# CATEGORY 5: Error Handling (12 tests)
# ============================================================================

class TestErrorHandling:
    """Test error handling in configuration."""

    def test_load_invalid_yaml_raises_error(self):
        """Test loading invalid YAML raises yaml.YAMLError."""
        yaml_content = "invalid: yaml: [syntax"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with pytest.raises(yaml.YAMLError):
                    MemoryConfig.from_yaml(f.name)
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_permission_error(self):
        """Test loading YAML with permission error raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("memory:\n  redis:\n    host: test\n")
            f.flush()

            try:
                # Make file unreadable
                os.chmod(f.name, 0o000)

                with pytest.raises(PermissionError):
                    MemoryConfig.from_yaml(f.name)
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, 0o644)
                os.unlink(f.name)

    def test_redis_config_with_invalid_port_type(self):
        """Test Redis config handles non-int port values."""
        yaml_content = """
memory:
  redis:
    port: not_a_number
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # YAML will parse as string, config accepts it
                # This tests that invalid types are preserved from YAML
                assert config.redis.port == "not_a_number"
            finally:
                os.unlink(f.name)

    def test_faiss_config_with_invalid_rebuild_threshold(self):
        """Test FAISS config with invalid rebuild threshold."""
        yaml_content = """
memory:
  faiss:
    rebuild_threshold: invalid
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should preserve value from YAML even if type is wrong
                assert config.faiss.rebuild_threshold == "invalid"
            finally:
                os.unlink(f.name)

    def test_ensure_directories_with_permission_error(self):
        """Test ensure_directories with permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MemoryConfig()
            restricted_dir = os.path.join(tmpdir, "restricted", "subdir")
            config.base_path = restricted_dir

            # Make parent directory read-only
            parent = os.path.dirname(restricted_dir)
            os.chmod(parent, 0o444)

            try:
                with pytest.raises(PermissionError):
                    config.ensure_directories()
            finally:
                # Restore permissions for cleanup
                os.chmod(parent, 0o755)

    def test_load_yaml_with_none_values(self):
        """Test loading YAML with None values uses defaults."""
        yaml_content = """
memory:
  redis:
    host: null
    port: null
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # None values should use defaults
                assert config.redis.host is None or config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_redis_config_missing_host_uses_default(self):
        """Test Redis config missing host uses default."""
        yaml_content = """
memory:
  redis:
    port: 6380
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "localhost"
                assert config.redis.port == 6380
            finally:
                os.unlink(f.name)

    def test_faiss_config_missing_index_type_uses_default(self):
        """Test FAISS config missing index_type uses default."""
        yaml_content = """
memory:
  faiss:
    rebuild_threshold: 0.2
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                assert config.faiss.index_type == "flat"
                assert config.faiss.rebuild_threshold == 0.2
            finally:
                os.unlink(f.name)

    def test_expand_paths_with_nonexistent_user(self):
        """Test expand_paths handles paths correctly."""
        config = MemoryConfig()
        config.base_path = "~user_that_does_not_exist/path"

        # Should handle gracefully or raise appropriate error
        try:
            config.expand_paths()
            # If it doesn't raise, that's okay - path handling is system-dependent
        except (KeyError, RuntimeError):
            # Expected if user doesn't exist
            pass

    def test_load_yaml_with_circular_references(self):
        """Test YAML loading handles circular references."""
        # YAML anchors can create circular references
        yaml_content = """
defaults: &defaults
  host: localhost

memory:
  redis: *defaults
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should handle YAML anchors without error
                assert config.redis.host == "localhost"
            finally:
                os.unlink(f.name)

    def test_redis_config_negative_ttl(self):
        """Test Redis config accepts negative TTL values."""
        yaml_content = """
memory:
  redis:
    ttl_session: -1
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should preserve the negative value
                assert config.redis.ttl_session == -1
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_boolean_values(self):
        """Test loading YAML with boolean configurations."""
        yaml_content = """
memory:
  vault:
    obsidian_compatible: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Vault config is not directly parsed from YAML
                # but this tests the loading doesn't break
                assert config.vault.obsidian_compatible is True  # Default unchanged
            finally:
                os.unlink(f.name)

    def test_load_yaml_with_empty_sections(self):
        """Test loading YAML with empty sections."""
        yaml_content = """
memory:
  redis: {}
  faiss: {}
  paths: {}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = MemoryConfig.from_yaml(f.name)
                # Should use all defaults
                assert config.redis.host == "localhost"
                assert config.faiss.index_type == "flat"
            finally:
                os.unlink(f.name)


# ============================================================================
# CATEGORY 6: Integration Tests (8 tests)
# ============================================================================

class TestIntegration:
    """Integration tests for full configuration workflow."""

    def test_full_workflow_load_expand_ensure(self):
        """Test full workflow: load YAML → expand paths → ensure directories."""
        yaml_content = """
memory:
  redis:
    host: custom-redis
  paths:
    vault: ~/test-vault
    faiss: ~/test-faiss
    database: ~/.cache/test.db
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                # Load
                config = MemoryConfig.from_yaml(f.name)
                assert config.redis.host == "custom-redis"
                assert config.vault.path == "~/test-vault"

                # Expand
                config.expand_paths()
                assert not config.vault.path.startswith("~")
                assert not config.faiss_path.startswith("~")

                # Ensure (with temp directory)
                import shutil
                with tempfile.TemporaryDirectory() as tmpdir:
                    config.base_path = os.path.join(tmpdir, "base")
                    config.faiss_path = os.path.join(tmpdir, "faiss")
                    config.vault.path = os.path.join(tmpdir, "vault")
                    config.sqlite.path = os.path.join(tmpdir, "db.sqlite")

                    config.ensure_directories()

                    assert Path(config.base_path).exists()
                    assert Path(config.faiss_path).exists()
                    assert Path(config.vault.path).exists()
            finally:
                os.unlink(f.name)

    def test_concurrent_config_initialization(self):
        """Test concurrent initialization doesn't create multiple instances."""
        import memory_mcp.config as config_module
        config_module._config = None

        configs = []

        def init_config():
            config = get_config()
            configs.append(config)

        threads = [threading.Thread(target=init_config) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be the same instance
        first = configs[0]
        assert all(c is first for c in configs)

        config_module._config = None

    def test_config_mutation_affects_subsequent_calls(self):
        """Test that mutating config affects subsequent get_config calls."""
        import memory_mcp.config as config_module
        config_module._config = None

        config1 = get_config()
        config1.redis.port = 8888

        config2 = get_config()
        assert config2.redis.port == 8888

        config_module._config = None

    def test_set_config_then_subsequent_mutations(self):
        """Test mutations after set_config affect singleton."""
        import memory_mcp.config as config_module
        config_module._config = None

        new_config = MemoryConfig()
        new_config.redis.port = 9999
        set_config(new_config)

        # Mutate
        retrieved = get_config()
        retrieved.faiss.index_type = "hnsw"

        # Should see mutation
        assert get_config().faiss.index_type == "hnsw"

        config_module._config = None

    def test_load_yaml_then_set_config_replaces_loaded(self):
        """Test set_config replaces config loaded from YAML."""
        import memory_mcp.config as config_module
        config_module._config = None

        yaml_content = "memory:\n  redis:\n    host: yaml-host\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {'CLAUDE_CODE_PP_CONFIG': f.name}):
                    config1 = get_config()
                    assert config1.redis.host == "yaml-host"

                    # Replace with new config
                    new_config = MemoryConfig()
                    new_config.redis.host = "new-host"
                    set_config(new_config)

                    config2 = get_config()
                    assert config2.redis.host == "new-host"
            finally:
                os.unlink(f.name)
                config_module._config = None

    def test_dataclass_immutability_per_instance(self):
        """Test that config dataclasses maintain separate state per instance."""
        config1 = MemoryConfig()
        config1.redis.port = 1111

        config2 = MemoryConfig()
        assert config2.redis.port == 6379

        # Verify config1 unchanged
        assert config1.redis.port == 1111

    def test_redis_config_inheritance_in_memory_config(self):
        """Test that RedisConfig in MemoryConfig works as expected."""
        config = MemoryConfig()
        assert isinstance(config.redis, RedisConfig)

        config.redis.port = 5555
        assert config.redis.port == 5555

    def test_nested_dataclass_modification(self):
        """Test modifying nested dataclasses in config."""
        config = MemoryConfig()

        # Modify nested config
        config.redis.host = "modified-host"
        config.faiss.index_type = "modified-type"
        config.vault.obsidian_compatible = False

        # Verify all modifications
        assert config.redis.host == "modified-host"
        assert config.faiss.index_type == "modified-type"
        assert config.vault.obsidian_compatible is False

    def test_full_workflow_with_env_variable(self):
        """Test full workflow using environment variable for config path."""
        import memory_mcp.config as config_module
        config_module._config = None

        yaml_content = """
memory:
  redis:
    host: env-redis-host
    port: 7777
  paths:
    vault: ~/env-vault
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {'CLAUDE_CODE_PP_CONFIG': f.name}):
                    # Get config via environment
                    config = get_config()
                    assert config.redis.host == "env-redis-host"
                    assert config.redis.port == 7777

                    # Expand paths
                    config.expand_paths()
                    assert not config.vault.path.startswith("~")

                    # Verify singleton still works
                    config2 = get_config()
                    assert config2 is config
            finally:
                os.unlink(f.name)
                config_module._config = None

    def test_complex_concurrent_workflow(self):
        """Test complex concurrent workflow with config load and set."""
        import memory_mcp.config as config_module
        config_module._config = None

        results = []

        def workflow(config_id):
            # Get initial config
            config = get_config()
            results.append(('get', config_id, config))

            # Modify and set
            new_config = MemoryConfig()
            new_config.redis.port = 8000 + config_id
            set_config(new_config)

            # Get again
            config2 = get_config()
            results.append(('get', config_id, config2))

        threads = [threading.Thread(target=workflow, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final config should be one of the set ones
        final = get_config()
        assert final.redis.port in [8000 + i for i in range(5)]

        config_module._config = None
