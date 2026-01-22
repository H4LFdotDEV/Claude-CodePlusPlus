# conftest.py
# Pytest fixtures for memory_mcp tests

import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_mcp.config import (
    MemoryConfig,
    RedisConfig,
    FAISSConfig,
    SQLiteConfig,
    VaultConfig,
    EmbeddingConfig,
    set_config,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration with temporary paths."""
    config = MemoryConfig(
        redis=RedisConfig(
            host="localhost",
            port=6379,
            db=15,  # Use database 15 for tests
            ttl_session=60,
            ttl_templates=60,
            ttl_queries=60,
        ),
        faiss=FAISSConfig(
            index_type="flat",
            dimension=768,
            rebuild_threshold=0.1,
        ),
        sqlite=SQLiteConfig(
            path=os.path.join(temp_dir, "test_memories.db"),
        ),
        vault=VaultConfig(
            path=os.path.join(temp_dir, "vault"),
            obsidian_compatible=True,
        ),
        embedding=EmbeddingConfig(
            provider="local",
            local_model="nomic-embed-text",
            local_endpoint="http://localhost:11434",
            fallback_order=["local"],
        ),
        base_path=temp_dir,
        faiss_path=os.path.join(temp_dir, "faiss"),
    )
    config.ensure_directories()
    set_config(config)
    return config


@pytest.fixture
def sqlite_index(test_config):
    """Create a SQLite index for testing."""
    from memory_mcp.sqlite_index import SQLiteIndex
    return SQLiteIndex(config=test_config.sqlite)


@pytest.fixture
def vault_manager(test_config):
    """Create a VaultManager for testing."""
    from memory_mcp.vault_manager import VaultManager
    return VaultManager(config=test_config.vault)


@pytest.fixture
def sample_document():
    """Create a sample MemoryDocument."""
    from memory_mcp.sqlite_index import MemoryDocument
    return MemoryDocument(
        id="test-doc-001",
        content="This is a test document with some content for testing.",
        doc_type="note",
        source="test/source.py",
        project="test-project",
        tags=["test", "sample"],
        metadata={"key": "value"},
    )


@pytest.fixture
def sample_documents():
    """Create multiple sample documents."""
    from memory_mcp.sqlite_index import MemoryDocument
    return [
        MemoryDocument(
            id=f"test-doc-{i:03d}",
            content=f"Test document {i} with unique content about {topic}.",
            doc_type=doc_type,
            source=f"test/file{i}.py",
            project="test-project",
            tags=["test", topic],
        )
        for i, (topic, doc_type) in enumerate([
            ("python", "code"),
            ("javascript", "code"),
            ("documentation", "note"),
            ("api reference", "reference"),
            ("chat history", "conversation"),
        ])
    ]


@pytest.fixture
def mock_redis():
    """Mock Redis client for tests without Redis."""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.keys.return_value = []
    mock.lpush.return_value = 1
    mock.lrange.return_value = []
    mock.info.return_value = {
        "used_memory_human": "1M",
        "used_memory_peak_human": "2M",
    }
    return mock


@pytest.fixture
def mock_faiss():
    """Mock FAISS index for tests without FAISS."""
    mock = MagicMock()
    mock.ntotal = 0
    mock.add.return_value = None
    mock.search.return_value = (
        [[0.1, 0.2, 0.3]],  # distances
        [[0, 1, 2]],  # indices
    )
    return mock


@pytest.fixture
def mock_embedding():
    """Mock embedding for tests."""
    import numpy as np
    return np.random.rand(768).astype(np.float32)


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider."""
    import numpy as np
    mock = MagicMock()
    mock.embed.return_value = np.random.rand(768).astype(np.float32)
    mock.embed_batch.return_value = [
        np.random.rand(768).astype(np.float32) for _ in range(5)
    ]
    mock.dimension = 768
    mock.name = "mock/test"
    return mock


@pytest.fixture
def sample_session_state():
    """Create a sample SessionState."""
    from memory_mcp.redis_client import SessionState

    now = datetime.now(timezone.utc).isoformat()
    return SessionState(
        session_id="test-session-001",
        project_path="test/project",  # Relative path (no leading /)
        active_files=["file1.py", "file2.py"],
        recent_queries=["query1", "query2"],
        context_window=[{"role": "user", "content": "test", "timestamp": now}],
        created_at=now,
        updated_at=now,
    )


# Environment setup for tests
@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    # Store original values
    original_env = {}
    keys_to_clean = [
        "OPENAI_API_KEY",
        "VOYAGE_API_KEY",
        "CLAUDE_CODE_PP_CONFIG",
    ]
    for key in keys_to_clean:
        original_env[key] = os.environ.get(key)

    yield

    # Restore original values
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
