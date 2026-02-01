# benchmarks/conftest.py
# Pytest configuration for benchmark tests

import os
import tempfile
import shutil
import pytest


def pytest_configure(config):
    """Register benchmark markers."""
    config.addinivalue_line(
        "markers", "benchmark: mark test as a benchmark"
    )


@pytest.fixture(scope="session")
def benchmark_temp_dir():
    """Create a temporary directory for benchmark tests."""
    tmp = tempfile.mkdtemp(prefix="memory_mcp_bench_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def benchmark_config(benchmark_temp_dir):
    """Create a test configuration for benchmarks."""
    from memory_mcp.config import (
        MemoryConfig, RedisConfig, SQLiteConfig, VaultConfig,
        EmbeddingConfig, GraphitiConfig, LivegrepConfig, set_config
    )

    config = MemoryConfig(
        redis=RedisConfig(
            host="localhost",
            port=6379,
            db=15,
            ttl_session=60,
            ttl_templates=60,
            ttl_queries=60,
        ),
        sqlite=SQLiteConfig(
            path=os.path.join(benchmark_temp_dir, "bench_memories.db"),
        ),
        vault=VaultConfig(
            path=os.path.join(benchmark_temp_dir, "vault"),
            obsidian_compatible=True,
        ),
        embedding=EmbeddingConfig(
            provider="local",
            local_model="nomic-embed-text",
            local_endpoint="http://localhost:11434",
            fallback_order=["local"],
        ),
        graphiti=GraphitiConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            enabled=False,
        ),
        livegrep=LivegrepConfig(
            endpoint="http://localhost:8910",
            enabled=False,
        ),
        base_path=benchmark_temp_dir,
    )
    config.ensure_directories()
    set_config(config)
    return config


@pytest.fixture(scope="session")
def benchmark_server(benchmark_config):
    """Create a shared server instance for benchmarks."""
    from memory_mcp.server import MemoryMCPServer
    server = MemoryMCPServer(config=benchmark_config)
    yield server
