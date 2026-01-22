# embedding_provider.py
# Embedding Provider for Claude Code++ Memory System
# Jeremiah Kroesche | Halfservers LLC
#
# Supports multiple embedding backends: local (Ollama), OpenAI, Voyage

import logging
import os
import json
import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .config import get_config, EmbeddingConfig


class EmbeddingProvider(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embeddings via Ollama."""

    def __init__(self, model: str = "nomic-embed-text", endpoint: str = "http://localhost:11434"):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is not installed. Run: pip install httpx")

        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self._dimension: Optional[int] = None
        self._client = httpx.Client(timeout=30.0)

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding using Ollama."""
        response = self._client.post(
            f"{self.endpoint}/api/embeddings",
            json={"model": self.model, "prompt": text}
        )
        response.raise_for_status()
        data = response.json()

        embedding = np.array(data["embedding"], dtype=np.float32)

        if self._dimension is None:
            self._dimension = len(embedding)

        return embedding

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Ollama doesn't support batch, so we process sequentially."""
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # Probe with empty string to get dimension
            self.embed("")
        return self._dimension or 768

    @property
    def name(self) -> str:
        return f"local/{self.model}"

    def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = self._client.get(f"{self.endpoint}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama health check failed: {e}")
            return False


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings."""

    DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536
    }

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is not installed. Run: pip install httpx")

        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding using OpenAI."""
        response = self._client.post(
            "/embeddings",
            json={"model": self.model, "input": text}
        )
        response.raise_for_status()
        data = response.json()

        return np.array(data["data"][0]["embedding"], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts."""
        response = self._client.post(
            "/embeddings",
            json={"model": self.model, "input": texts}
        )
        response.raise_for_status()
        data = response.json()

        # Sort by index to maintain order
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [np.array(e["embedding"], dtype=np.float32) for e in embeddings_data]

    @property
    def dimension(self) -> int:
        return self.DIMENSIONS.get(self.model, 1536)

    @property
    def name(self) -> str:
        return f"openai/{self.model}"


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embeddings (optimized for code)."""

    DIMENSIONS = {
        "voyage-code-2": 1536,
        "voyage-2": 1024,
        "voyage-large-2": 1536
    }

    def __init__(self, model: str = "voyage-code-2", api_key: Optional[str] = None):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is not installed. Run: pip install httpx")

        self.model = model
        self.api_key = api_key or os.environ.get("VOYAGE_API_KEY")
        if not self.api_key:
            raise ValueError("Voyage API key required")

        self._client = httpx.Client(
            base_url="https://api.voyageai.com/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding using Voyage."""
        response = self._client.post(
            "/embeddings",
            json={"model": self.model, "input": text}
        )
        response.raise_for_status()
        data = response.json()

        return np.array(data["data"][0]["embedding"], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts."""
        response = self._client.post(
            "/embeddings",
            json={"model": self.model, "input": texts}
        )
        response.raise_for_status()
        data = response.json()

        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [np.array(e["embedding"], dtype=np.float32) for e in embeddings_data]

    @property
    def dimension(self) -> int:
        return self.DIMENSIONS.get(self.model, 1536)

    @property
    def name(self) -> str:
        return f"voyage/{self.model}"


class FallbackEmbeddingProvider(EmbeddingProvider):
    """Fallback provider that tries multiple backends."""

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or get_config().embedding
        self._providers: List[EmbeddingProvider] = []
        self._active_provider: Optional[EmbeddingProvider] = None

        self._init_providers()

    def _init_providers(self):
        """Initialize providers based on fallback order."""
        for provider_name in self.config.fallback_order:
            try:
                if provider_name == "local":
                    provider = LocalEmbeddingProvider(
                        model=self.config.local_model,
                        endpoint=self.config.local_endpoint
                    )
                    if provider.health_check():
                        self._providers.append(provider)
                elif provider_name == "openai":
                    if os.environ.get("OPENAI_API_KEY"):
                        self._providers.append(OpenAIEmbeddingProvider(
                            model=self.config.openai_model
                        ))
                elif provider_name == "voyage":
                    if os.environ.get("VOYAGE_API_KEY"):
                        self._providers.append(VoyageEmbeddingProvider(
                            model=self.config.voyage_model
                        ))
            except Exception as e:
                logger.debug(f"Failed to initialize {provider_name} provider: {e}")
                continue

        if self._providers:
            self._active_provider = self._providers[0]

    def _get_working_provider(self) -> EmbeddingProvider:
        """Get first working provider."""
        for provider in self._providers:
            try:
                if isinstance(provider, LocalEmbeddingProvider):
                    if provider.health_check():
                        self._active_provider = provider
                        return provider
                else:
                    self._active_provider = provider
                    return provider
            except Exception as e:
                logger.debug(f"Provider {provider.name} unavailable: {e}")
                continue

        raise RuntimeError("No embedding providers available")

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding with fallback."""
        errors = []
        for provider in self._providers:
            try:
                result = provider.embed(text)
                self._active_provider = provider
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                continue

        raise RuntimeError(f"All providers failed: {'; '.join(errors)}")

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings with fallback."""
        errors = []
        for provider in self._providers:
            try:
                result = provider.embed_batch(texts)
                self._active_provider = provider
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                continue

        raise RuntimeError(f"All providers failed: {'; '.join(errors)}")

    @property
    def dimension(self) -> int:
        if self._active_provider:
            return self._active_provider.dimension
        return 768  # Default

    @property
    def name(self) -> str:
        if self._active_provider:
            return f"fallback({self._active_provider.name})"
        return "fallback(none)"

    @property
    def available_providers(self) -> List[str]:
        return [p.name for p in self._providers]


def get_embedding_provider(config: Optional[EmbeddingConfig] = None) -> EmbeddingProvider:
    """Factory function to get appropriate embedding provider."""
    config = config or get_config().embedding

    if config.provider == "local":
        return LocalEmbeddingProvider(
            model=config.local_model,
            endpoint=config.local_endpoint
        )
    elif config.provider == "openai":
        return OpenAIEmbeddingProvider(model=config.openai_model)
    elif config.provider == "voyage":
        return VoyageEmbeddingProvider(model=config.voyage_model)
    else:
        # Default to fallback
        return FallbackEmbeddingProvider(config)
