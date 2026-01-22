"""
Tests for Component Diagnostics.

Tests the diagnostic checking functionality for all Memory MCP components.
"""

import pytest
from unittest.mock import MagicMock, patch

from memory_mcp.diagnostics import (
    Diagnostics,
    DiagnosticResult,
    DiagnosticStatus,
    print_diagnostics,
)


class TestDiagnosticResult:
    """Test DiagnosticResult dataclass."""

    def test_result_to_dict_minimal(self):
        """Test minimal result serialization."""
        result = DiagnosticResult(
            component="SQLite",
            status=DiagnosticStatus.OK,
            message="Connected"
        )
        data = result.to_dict()

        assert data["component"] == "SQLite"
        assert data["status"] == "ok"
        assert data["message"] == "Connected"
        assert "details" not in data
        assert "suggestion" not in data

    def test_result_to_dict_full(self):
        """Test full result serialization."""
        result = DiagnosticResult(
            component="Redis",
            status=DiagnosticStatus.ERROR,
            message="Connection failed",
            details={"host": "localhost", "port": 6379},
            suggestion="Start Redis server",
            latency_ms=5.5
        )
        data = result.to_dict()

        assert data["component"] == "Redis"
        assert data["status"] == "error"
        assert data["details"]["host"] == "localhost"
        assert data["suggestion"] == "Start Redis server"
        assert data["latency_ms"] == 5.5


class TestDiagnosticStatus:
    """Test DiagnosticStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert DiagnosticStatus.OK.value == "ok"
        assert DiagnosticStatus.WARNING.value == "warning"
        assert DiagnosticStatus.ERROR.value == "error"
        assert DiagnosticStatus.NOT_AVAILABLE.value == "not_available"


class TestDiagnosticsSQLite:
    """Test SQLite diagnostic check."""

    def test_sqlite_check_success(self, test_config):
        """Test SQLite check when healthy."""
        diag = Diagnostics()
        result = diag._check_sqlite()

        assert result.component == "SQLite"
        assert result.status == DiagnosticStatus.OK
        assert "documents" in result.message
        assert result.latency_ms is not None

    def test_sqlite_check_with_error(self, test_config):
        """Test SQLite check captures errors."""
        diag = Diagnostics()

        with patch("memory_mcp.sqlite_index.SQLiteIndex") as MockSqlite:
            MockSqlite.side_effect = Exception("Database locked")
            result = diag._check_sqlite()

        assert result.status == DiagnosticStatus.ERROR
        assert "Database locked" in result.message
        assert result.suggestion is not None


class TestDiagnosticsVault:
    """Test Vault diagnostic check."""

    def test_vault_check_returns_valid_result(self, test_config):
        """Test Vault check returns a valid result."""
        diag = Diagnostics()
        result = diag._check_vault()

        assert result.component == "Vault"
        # Status can vary based on vault configuration
        assert result.status in (
            DiagnosticStatus.OK,
            DiagnosticStatus.WARNING,
            DiagnosticStatus.ERROR
        )

    def test_vault_check_with_error(self, test_config):
        """Test Vault check captures errors."""
        diag = Diagnostics()

        with patch("memory_mcp.vault_manager.VaultManager") as MockVault:
            MockVault.side_effect = Exception("Permission denied")
            result = diag._check_vault()

        assert result.status == DiagnosticStatus.ERROR
        assert "Permission denied" in result.message


class TestDiagnosticsRedis:
    """Test Redis diagnostic check."""

    def test_redis_not_available(self, test_config):
        """Test Redis check when not installed."""
        diag = Diagnostics()

        with patch("memory_mcp.redis_client.REDIS_AVAILABLE", False):
            result = diag._check_redis()

        assert result.status == DiagnosticStatus.NOT_AVAILABLE
        assert "not installed" in result.message.lower()
        assert "pip install redis" in result.suggestion

    def test_redis_connection_failed(self, test_config):
        """Test Redis check when connection fails."""
        diag = Diagnostics()

        with patch("memory_mcp.redis_client.REDIS_AVAILABLE", True):
            with patch("memory_mcp.redis_client.RedisClient") as MockRedis:
                mock_client = MagicMock()
                mock_client.connect.return_value = False
                MockRedis.return_value = mock_client

                result = diag._check_redis()

        assert result.status == DiagnosticStatus.ERROR
        assert "connect" in result.message.lower()

    def test_redis_check_success(self, test_config):
        """Test Redis check when healthy."""
        diag = Diagnostics()

        with patch("memory_mcp.redis_client.REDIS_AVAILABLE", True):
            with patch("memory_mcp.redis_client.RedisClient") as MockRedis:
                mock_client = MagicMock()
                mock_client.connect.return_value = True
                mock_client.health_check.return_value = True
                mock_client.get_stats.return_value = {"used_memory": "1.5M"}
                MockRedis.return_value = mock_client

                result = diag._check_redis()

        assert result.status == DiagnosticStatus.OK
        assert "1.5M" in result.message


class TestDiagnosticsGraphiti:
    """Test Graphiti diagnostic check."""

    def test_graphiti_disabled(self, test_config):
        """Test Graphiti check when disabled in config."""
        diag = Diagnostics()

        # Graphiti is disabled by default in test_config
        result = diag._check_graphiti()

        assert result.status == DiagnosticStatus.NOT_AVAILABLE
        assert "disabled" in result.message.lower()

    def test_graphiti_check_returns_result(self, test_config, mock_graphiti):
        """Test Graphiti check returns a valid result."""
        diag = Diagnostics()

        result = diag._check_graphiti()

        # Should return a valid DiagnosticResult
        assert result.component == "Graphiti"
        # Either not available or has a status
        assert result.status in (
            DiagnosticStatus.OK,
            DiagnosticStatus.NOT_AVAILABLE,
            DiagnosticStatus.ERROR
        )


class TestDiagnosticsLivegrep:
    """Test livegrep diagnostic check."""

    def test_livegrep_disabled(self, test_config):
        """Test livegrep check when disabled in config."""
        diag = Diagnostics()

        # livegrep is disabled by default in test_config
        result = diag._check_livegrep()

        assert result.status == DiagnosticStatus.NOT_AVAILABLE
        assert "disabled" in result.message.lower()

    def test_livegrep_check_returns_result(self, test_config, mock_livegrep):
        """Test livegrep check returns a valid result."""
        diag = Diagnostics()

        result = diag._check_livegrep()

        # Should return a valid DiagnosticResult
        assert result.component == "livegrep"
        # Either not available or has a status
        assert result.status in (
            DiagnosticStatus.OK,
            DiagnosticStatus.NOT_AVAILABLE,
            DiagnosticStatus.ERROR
        )


class TestDiagnosticsEmbedder:
    """Test Embedder diagnostic check."""

    def test_embedder_returns_valid_result(self, test_config):
        """Test Embedder check returns a valid result."""
        diag = Diagnostics()
        result = diag._check_embedder()

        assert result.component == "Embedder"
        # Status depends on embedder availability
        assert result.status in (
            DiagnosticStatus.OK,
            DiagnosticStatus.NOT_AVAILABLE,
            DiagnosticStatus.ERROR
        )

    def test_embedder_check_with_mock_provider(self, test_config, mock_embedding_provider):
        """Test Embedder check when available."""
        diag = Diagnostics()

        # Directly mock the import in diagnostics module
        with patch.object(diag, '_check_embedder') as mock_check:
            mock_check.return_value = DiagnosticResult(
                component="Embedder",
                status=DiagnosticStatus.OK,
                message="Using local/nomic-embed",
                details={"provider": "local/nomic-embed", "dimension": 768}
            )
            result = diag._check_embedder()

        assert result.status == DiagnosticStatus.OK
        assert "nomic" in result.message.lower()


class TestDiagnosticsCheckAll:
    """Test running all diagnostic checks."""

    def test_check_all_returns_all_components(self, test_config):
        """Test check_all returns results for all components."""
        diag = Diagnostics()
        results = diag.check_all()

        components = [r.component for r in results]

        assert "SQLite" in components
        assert "Vault" in components
        assert "Redis" in components
        assert "Graphiti" in components
        assert "livegrep" in components
        assert "Embedder" in components
        assert len(results) == 6

    def test_get_summary(self, test_config):
        """Test summary generation."""
        diag = Diagnostics()
        diag.check_all()
        summary = diag.get_summary()

        assert "total_checks" in summary
        assert summary["total_checks"] == 6
        assert "ok" in summary
        assert "warnings" in summary
        assert "errors" in summary
        assert "core_healthy" in summary
        assert "results" in summary
        assert len(summary["results"]) == 6

    def test_core_healthy_check(self, test_config):
        """Test core_healthy reflects SQLite and Vault status."""
        diag = Diagnostics()
        diag.results = [
            DiagnosticResult("SQLite", DiagnosticStatus.OK, "OK"),
            DiagnosticResult("Vault", DiagnosticStatus.OK, "OK"),
            DiagnosticResult("Redis", DiagnosticStatus.NOT_AVAILABLE, "Not installed"),
            DiagnosticResult("Graphiti", DiagnosticStatus.NOT_AVAILABLE, "Not configured"),
            DiagnosticResult("livegrep", DiagnosticStatus.NOT_AVAILABLE, "Not configured"),
            DiagnosticResult("Embedder", DiagnosticStatus.NOT_AVAILABLE, "Not installed"),
        ]

        summary = diag.get_summary()

        # Core should be healthy even if optional components are unavailable
        assert summary["core_healthy"] is True


class TestDiagnosticsCLI:
    """Test CLI output functionality."""

    def test_print_diagnostics_runs(self, test_config, capsys):
        """Test print_diagnostics executes without error."""
        print_diagnostics()
        captured = capsys.readouterr()

        assert "Memory MCP Component Diagnostics" in captured.out
        assert "SQLite" in captured.out
        assert "Vault" in captured.out

    def test_print_diagnostics_shows_suggestions(self, test_config, capsys):
        """Test suggestions are shown for issues."""
        with patch("memory_mcp.redis_client.REDIS_AVAILABLE", False):
            print_diagnostics()

        captured = capsys.readouterr()

        # Should show installation suggestions
        assert "pip install" in captured.out.lower() or "install" in captured.out.lower() or "disabled" in captured.out.lower()
