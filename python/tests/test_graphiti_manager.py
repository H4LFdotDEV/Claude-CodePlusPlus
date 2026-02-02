# test_graphiti_manager.py
# Tests for GraphitiManager knowledge graph component
# Jeremiah Kroesche | Halfservers LLC

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Test imports
import sys
sys.path.insert(0, '/Users/jeremiah/Desktop/Claude Code++/claude-code/python')


class TestGraphitiManagerWithoutGraphiti:
    """Tests when graphiti-core is not installed."""

    def test_import_without_graphiti(self):
        """Test that module handles missing graphiti-core gracefully."""
        with patch.dict('sys.modules', {'graphiti_core': None}):
            # Reload to test import error handling
            from memory_mcp import graphiti_manager
            # Should not raise, just log warning
            assert hasattr(graphiti_manager, 'GraphitiManager')

    def test_manager_without_graphiti_available(self):
        """Test manager behavior when graphiti not available."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            manager = GraphitiManager()
            assert manager.health_check() is False


class TestGraphitiManagerInitialization:
    """Tests for GraphitiManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        from memory_mcp.graphiti_manager import GraphitiManager

        manager = GraphitiManager()

        assert manager.uri == "bolt://localhost:7687"
        assert manager.user == "neo4j"
        assert manager._initialized is False

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        from memory_mcp.graphiti_manager import GraphitiManager

        manager = GraphitiManager(
            uri="bolt://custom-host:7688",
            user="custom_user",
            password="custom_pass",
            openai_api_key="sk-test-key"
        )

        assert manager.uri == "bolt://custom-host:7688"
        assert manager.user == "custom_user"
        # Credentials are now accessed via private properties for security
        assert manager._password == "custom_pass"
        assert manager._openai_api_key == "sk-test-key"

    def test_init_from_environment(self, monkeypatch):
        """Test initialization reads from environment variables."""
        from memory_mcp.graphiti_manager import GraphitiManager

        # Clear any override env vars first
        monkeypatch.delenv("_GRAPHITI_OVERRIDE_PASSWORD", raising=False)
        monkeypatch.delenv("_GRAPHITI_OVERRIDE_OPENAI_KEY", raising=False)

        monkeypatch.setenv("NEO4J_URI", "bolt://env-host:7689")
        monkeypatch.setenv("NEO4J_USER", "env_user")
        monkeypatch.setenv("NEO4J_PASSWORD", "env_pass")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")

        manager = GraphitiManager()

        assert manager.uri == "bolt://env-host:7689"
        assert manager.user == "env_user"
        # Credentials are now accessed via private properties for security
        assert manager._password == "env_pass"
        assert manager._openai_api_key == "sk-env-key"


class TestGraphitiManagerDataClasses:
    """Tests for GraphitiManager data classes."""

    def test_entity_result_creation(self):
        """Test EntityResult dataclass."""
        from memory_mcp.graphiti_manager import EntityResult

        entity = EntityResult(
            id="test-id",
            name="Test Entity",
            summary="A test entity for testing",
            labels=["Person", "Developer"],
            created_at="2024-01-21T00:00:00Z"
        )

        assert entity.id == "test-id"
        assert entity.name == "Test Entity"
        assert entity.summary == "A test entity for testing"
        assert entity.labels == ["Person", "Developer"]
        assert entity.created_at == "2024-01-21T00:00:00Z"

    def test_fact_result_creation(self):
        """Test FactResult dataclass."""
        from memory_mcp.graphiti_manager import FactResult

        fact = FactResult(
            id="fact-id",
            source_entity="Claude",
            target_entity="Anthropic",
            fact="was created by",
            valid_at="2024-01-01T00:00:00Z",
            invalid_at=None
        )

        assert fact.id == "fact-id"
        assert fact.source_entity == "Claude"
        assert fact.target_entity == "Anthropic"
        assert fact.fact == "was created by"
        assert fact.valid_at == "2024-01-01T00:00:00Z"
        assert fact.invalid_at is None

    def test_episode_result_creation(self):
        """Test EpisodeResult dataclass."""
        from memory_mcp.graphiti_manager import EpisodeResult

        result = EpisodeResult(
            episode_id="ep-123",
            entities_extracted=5,
            relationships_extracted=3
        )

        assert result.episode_id == "ep-123"
        assert result.entities_extracted == 5
        assert result.relationships_extracted == 3


class TestGraphitiManagerMocked:
    """Tests with mocked Graphiti client."""

    @pytest.fixture
    def mock_graphiti(self):
        """Create a mock Graphiti instance."""
        mock = MagicMock()
        mock.build_indices_and_constraints = AsyncMock()
        mock.add_episode = AsyncMock()
        mock.search_nodes = AsyncMock()
        mock.search_edges = AsyncMock()
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_graphiti):
        """Test successful initialization."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            pytest.skip("graphiti-core not installed")

        with patch('memory_mcp.graphiti_manager.Graphiti', return_value=mock_graphiti):
            manager = GraphitiManager(password="test-pass")
            result = await manager.initialize()

            assert result is True
            assert manager._initialized is True
            mock_graphiti.build_indices_and_constraints.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_password(self):
        """Test initialization fails without password."""
        from memory_mcp.graphiti_manager import GraphitiManager

        manager = GraphitiManager(password=None)
        result = await manager.initialize()

        assert result is False
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_add_memory(self, mock_graphiti):
        """Test adding memory to knowledge graph."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            pytest.skip("graphiti-core not installed")

        mock_episode = MagicMock()
        mock_episode.uuid = "episode-123"
        mock_episode.entity_edges = ["e1", "e2"]
        mock_graphiti.add_episode = AsyncMock(return_value=mock_episode)

        with patch('memory_mcp.graphiti_manager.Graphiti', return_value=mock_graphiti):
            manager = GraphitiManager(password="test-pass")
            manager._initialized = True
            manager._graphiti = mock_graphiti

            result = await manager.add_memory(
                content="Claude is an AI assistant",
                source="test",
                doc_type="note"
            )

            assert result is not None
            assert result.episode_id == "episode-123"

    @pytest.mark.asyncio
    async def test_search_entities(self, mock_graphiti):
        """Test searching for entities."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            pytest.skip("graphiti-core not installed")

        mock_node = MagicMock()
        mock_node.uuid = "node-123"
        mock_node.name = "Claude"
        mock_node.summary = "An AI assistant"
        mock_node.labels = ["AI", "Assistant"]
        mock_graphiti.search_nodes = AsyncMock(return_value=[mock_node])

        with patch('memory_mcp.graphiti_manager.Graphiti', return_value=mock_graphiti):
            manager = GraphitiManager(password="test-pass")
            manager._initialized = True
            manager._graphiti = mock_graphiti

            results = await manager.search_entities("Claude")

            assert len(results) == 1
            assert results[0].name == "Claude"
            assert results[0].summary == "An AI assistant"

    @pytest.mark.asyncio
    async def test_search_facts(self, mock_graphiti):
        """Test searching for facts."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            pytest.skip("graphiti-core not installed")

        mock_edge = MagicMock()
        mock_edge.uuid = "edge-123"
        mock_edge.source_node_name = "Claude"
        mock_edge.target_node_name = "Anthropic"
        mock_edge.fact = "was created by"
        mock_edge.valid_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_edge.invalid_at = None
        mock_graphiti.search_edges = AsyncMock(return_value=[mock_edge])

        with patch('memory_mcp.graphiti_manager.Graphiti', return_value=mock_graphiti):
            manager = GraphitiManager(password="test-pass")
            manager._initialized = True
            manager._graphiti = mock_graphiti

            results = await manager.search_facts("created")

            assert len(results) == 1
            assert results[0].source_entity == "Claude"
            assert results[0].target_entity == "Anthropic"
            assert results[0].fact == "was created by"


class TestGraphitiManagerHealthCheck:
    """Tests for health check functionality."""

    def test_health_check_not_available(self):
        """Test health check when Graphiti not available."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if GRAPHITI_AVAILABLE:
            # Test with uninitialized manager
            manager = GraphitiManager()
            assert manager.health_check() is False
        else:
            manager = GraphitiManager()
            assert manager.health_check() is False


class TestGraphitiManagerStats:
    """Tests for statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_stats_not_initialized(self):
        """Test stats when not initialized."""
        from memory_mcp.graphiti_manager import GraphitiManager

        manager = GraphitiManager()
        stats = await manager.get_stats()

        assert stats["available"] is False
        assert "error" in stats or "Not initialized" in str(stats)

    @pytest.mark.asyncio
    async def test_get_stats_initialized(self):
        """Test stats when initialized."""
        from memory_mcp.graphiti_manager import GraphitiManager, GRAPHITI_AVAILABLE

        if not GRAPHITI_AVAILABLE:
            pytest.skip("graphiti-core not installed")

        mock_graphiti = MagicMock()
        mock_graphiti.build_indices_and_constraints = AsyncMock()

        with patch('memory_mcp.graphiti_manager.Graphiti', return_value=mock_graphiti):
            manager = GraphitiManager(password="test-pass")
            manager._initialized = True
            manager._graphiti = mock_graphiti

            stats = await manager.get_stats()

            assert stats["available"] is True
            assert stats["initialized"] is True
            assert "uri" in stats
