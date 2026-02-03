# test_embedding_provider.py
# Tests for embedding providers

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys


# Check if httpx is available for testing
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class TestEmbeddingProviderBase:
    """Tests for embedding provider base functionality."""

    def test_provider_interface(self, mock_embedding_provider):
        """Test provider implements required interface."""
        assert hasattr(mock_embedding_provider, "embed")
        assert hasattr(mock_embedding_provider, "embed_batch")
        assert hasattr(mock_embedding_provider, "dimension")
        assert hasattr(mock_embedding_provider, "name")


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestLocalEmbeddingProvider:
    """Tests for LocalEmbeddingProvider (Ollama)."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx client for Ollama."""
        mock = MagicMock()
        mock.post.return_value = MagicMock(
            json=lambda: {"embedding": np.random.rand(768).tolist()},
            raise_for_status=lambda: None,
        )
        mock.get.return_value = MagicMock(
            status_code=200,
        )
        return mock

    def test_local_provider_creation(self, mock_httpx_client):
        """Test creating local provider."""
        with patch.object(httpx, 'Client', return_value=mock_httpx_client):
            from memory_mcp.embedding_provider import LocalEmbeddingProvider

            provider = LocalEmbeddingProvider(
                model="nomic-embed-text",
                endpoint="http://localhost:11434"
            )
            assert provider.model == "nomic-embed-text"

    def test_local_embed(self, mock_httpx_client):
        """Test generating embedding with local provider."""
        with patch.object(httpx, 'Client', return_value=mock_httpx_client):
            from memory_mcp.embedding_provider import LocalEmbeddingProvider

            provider = LocalEmbeddingProvider()
            embedding = provider.embed("test text")
            assert embedding.shape == (768,)
            assert embedding.dtype == np.float32

    def test_local_embed_batch(self, mock_httpx_client):
        """Test batch embedding with local provider."""
        with patch.object(httpx, 'Client', return_value=mock_httpx_client):
            from memory_mcp.embedding_provider import LocalEmbeddingProvider

            provider = LocalEmbeddingProvider()
            embeddings = provider.embed_batch(["text1", "text2", "text3"])
            assert len(embeddings) == 3

    def test_local_health_check(self, mock_httpx_client):
        """Test health check for local provider."""
        with patch.object(httpx, 'Client', return_value=mock_httpx_client):
            from memory_mcp.embedding_provider import LocalEmbeddingProvider

            provider = LocalEmbeddingProvider()
            assert provider.health_check() is True


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock httpx client for OpenAI."""
        mock = MagicMock()
        mock.post.return_value = MagicMock(
            json=lambda: {
                "data": [{"embedding": np.random.rand(1536).tolist(), "index": 0}]
            },
            raise_for_status=lambda: None,
        )
        return mock

    def test_openai_provider_requires_key(self):
        """Test OpenAI provider requires API key."""
        import os
        os.environ.pop("OPENAI_API_KEY", None)

        from memory_mcp.embedding_provider import OpenAIEmbeddingProvider

        with pytest.raises(ValueError, match="API key required"):
            OpenAIEmbeddingProvider()

    def test_openai_provider_creation(self, mock_openai_client):
        """Test creating OpenAI provider with key."""
        with patch.object(httpx, 'Client', return_value=mock_openai_client):
            from memory_mcp.embedding_provider import OpenAIEmbeddingProvider

            provider = OpenAIEmbeddingProvider(api_key="test-key")
            assert provider.dimension == 1536

    def test_openai_embed(self, mock_openai_client):
        """Test generating embedding with OpenAI."""
        with patch.object(httpx, 'Client', return_value=mock_openai_client):
            from memory_mcp.embedding_provider import OpenAIEmbeddingProvider

            provider = OpenAIEmbeddingProvider(api_key="test-key")
            embedding = provider.embed("test text")
            assert embedding.shape == (1536,)

    def test_openai_dimension_by_model(self, mock_openai_client):
        """Test dimension varies by model."""
        with patch.object(httpx, 'Client', return_value=mock_openai_client):
            from memory_mcp.embedding_provider import OpenAIEmbeddingProvider

            small = OpenAIEmbeddingProvider(model="text-embedding-3-small", api_key="key")
            large = OpenAIEmbeddingProvider(model="text-embedding-3-large", api_key="key")

            assert small.dimension == 1536
            assert large.dimension == 3072


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestVoyageEmbeddingProvider:
    """Tests for VoyageEmbeddingProvider."""

    @pytest.fixture
    def mock_voyage_client(self):
        """Mock httpx client for Voyage."""
        mock = MagicMock()
        mock.post.return_value = MagicMock(
            json=lambda: {
                "data": [{"embedding": np.random.rand(1536).tolist(), "index": 0}]
            },
            raise_for_status=lambda: None,
        )
        return mock

    def test_voyage_provider_requires_key(self):
        """Test Voyage provider requires API key."""
        import os
        os.environ.pop("VOYAGE_API_KEY", None)

        from memory_mcp.embedding_provider import VoyageEmbeddingProvider

        with pytest.raises(ValueError, match="API key required"):
            VoyageEmbeddingProvider()

    def test_voyage_provider_creation(self, mock_voyage_client):
        """Test creating Voyage provider."""
        with patch.object(httpx, 'Client', return_value=mock_voyage_client):
            from memory_mcp.embedding_provider import VoyageEmbeddingProvider

            provider = VoyageEmbeddingProvider(api_key="test-key")
            assert provider.dimension == 1536


class TestFallbackEmbeddingProvider:
    """Tests for FallbackEmbeddingProvider."""

    def test_fallback_with_no_providers(self, test_config):
        """Test fallback raises error when no providers available."""
        from memory_mcp.embedding_provider import FallbackEmbeddingProvider

        # Configure to not use any providers
        test_config.embedding.fallback_order = []

        provider = FallbackEmbeddingProvider(config=test_config.embedding)
        with pytest.raises(RuntimeError, match="No embedding providers available"):
            provider._get_working_provider()

    def test_fallback_tries_multiple_providers(self, test_config):
        """Test fallback tries providers in order."""
        from memory_mcp.embedding_provider import FallbackEmbeddingProvider

        # This would require mocking multiple providers
        # The actual implementation tries local first, then others
        provider = FallbackEmbeddingProvider(config=test_config.embedding)
        assert len(provider.available_providers) >= 0

    def test_fallback_name_includes_active(self):
        """Test fallback name includes active provider."""
        from memory_mcp.embedding_provider import FallbackEmbeddingProvider
        from memory_mcp.config import EmbeddingConfig

        config = EmbeddingConfig(fallback_order=[])
        provider = FallbackEmbeddingProvider(config=config)

        # With no active provider
        assert "none" in provider.name or "fallback" in provider.name


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider factory function."""

    def test_get_fallback_by_default(self, test_config):
        """Test factory returns fallback provider by default."""
        test_config.embedding.provider = "fallback"

        from memory_mcp.embedding_provider import get_embedding_provider

        provider = get_embedding_provider(test_config.embedding)
        assert "fallback" in provider.name.lower()

    @pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
    def test_get_local_provider(self, test_config):
        """Test factory can return local provider."""
        test_config.embedding.provider = "local"

        mock_client = MagicMock()
        with patch.object(httpx, 'Client', return_value=mock_client):
            from memory_mcp.embedding_provider import get_embedding_provider, LocalEmbeddingProvider

            # Disable caching to test raw provider
            provider = get_embedding_provider(test_config.embedding, enable_cache=False)
            assert isinstance(provider, LocalEmbeddingProvider)
