# test_livegrep_client.py
# Tests for LivegrepClient code search component
# Jeremiah Kroesche | Halfservers LLC

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

# Test imports
import sys
sys.path.insert(0, '/Users/jeremiah/Desktop/Claude Code++/claude-code/python')


class TestLivegrepDataClasses:
    """Tests for livegrep data classes."""

    def test_livegrep_result_creation(self):
        """Test LivegrepResult dataclass."""
        from memory_mcp.livegrep_client import LivegrepResult

        result = LivegrepResult(
            repo="my-project",
            path="src/main.py",
            line_number=42,
            line_content="def main():",
            context_before=["# Entry point"],
            context_after=["    pass"]
        )

        assert result.repo == "my-project"
        assert result.path == "src/main.py"
        assert result.line_number == 42
        assert result.line_content == "def main():"
        assert result.context_before == ["# Entry point"]
        assert result.context_after == ["    pass"]

    def test_livegrep_result_to_dict(self):
        """Test LivegrepResult.to_dict() method."""
        from memory_mcp.livegrep_client import LivegrepResult

        result = LivegrepResult(
            repo="test-repo",
            path="test.py",
            line_number=10,
            line_content="print('hello')",
            context_before=[],
            context_after=[]
        )

        d = result.to_dict()

        assert d["repo"] == "test-repo"
        assert d["path"] == "test.py"
        assert d["line"] == 10
        assert d["content"] == "print('hello')"

    def test_livegrep_search_response_creation(self):
        """Test LivegrepSearchResponse dataclass."""
        from memory_mcp.livegrep_client import LivegrepSearchResponse, LivegrepResult

        results = [
            LivegrepResult("repo", "file.py", 1, "line1", [], []),
            LivegrepResult("repo", "file.py", 2, "line2", [], []),
        ]

        response = LivegrepSearchResponse(
            results=results,
            total_matches=100,
            truncated=True,
            query="test query",
            duration_ms=45.5
        )

        assert len(response.results) == 2
        assert response.total_matches == 100
        assert response.truncated is True
        assert response.query == "test query"
        assert response.duration_ms == 45.5


class TestLivegrepClientInitialization:
    """Tests for LivegrepClient initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        from memory_mcp.livegrep_client import LivegrepClient

        client = LivegrepClient()

        assert client.endpoint == "http://localhost:8910"
        assert client.timeout == 30.0
        assert client._client is None

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        from memory_mcp.livegrep_client import LivegrepClient

        client = LivegrepClient(
            endpoint="http://custom-host:9000",
            timeout=60.0
        )

        assert client.endpoint == "http://custom-host:9000"
        assert client.timeout == 60.0

    def test_init_from_environment(self, monkeypatch):
        """Test initialization reads from environment variables."""
        from memory_mcp.livegrep_client import LivegrepClient

        monkeypatch.setenv("LIVEGREP_ENDPOINT", "http://env-host:8910")

        client = LivegrepClient()

        assert client.endpoint == "http://env-host:8910"

    def test_endpoint_trailing_slash_removed(self):
        """Test that trailing slash is removed from endpoint."""
        from memory_mcp.livegrep_client import LivegrepClient

        client = LivegrepClient(endpoint="http://localhost:8910/")

        assert client.endpoint == "http://localhost:8910"


class TestLivegrepClientSearch:
    """Tests for search functionality."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        mock = MagicMock()
        return mock

    def test_search_basic(self, mock_httpx_client):
        """Test basic search functionality."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "tree": "my-repo",
                    "path": "src/main.py",
                    "lno": 42,
                    "line": "def main():",
                    "context_before": [],
                    "context_after": []
                }
            ],
            "total_matches": 1,
            "truncated": False
        }
        # Mock the request method (used by _request_with_retry)
        mock_httpx_client.request.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_httpx_client):
            client = LivegrepClient()
            client._client = mock_httpx_client

            response = client.search("def main")

            assert len(response.results) == 1
            assert response.results[0].repo == "my-repo"
            assert response.results[0].path == "src/main.py"
            assert response.results[0].line_number == 42

    def test_search_with_path_filter(self, mock_httpx_client):
        """Test search with path filter."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "total_matches": 0, "truncated": False}
        mock_httpx_client.request.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_httpx_client):
            client = LivegrepClient()
            client._client = mock_httpx_client

            client.search("test", path_filter="*.py")

            # Check that path filter was included in query
            call_args = mock_httpx_client.request.call_args
            query = call_args.kwargs.get("params", {}).get("q", "")
            assert "path:*.py" in query

    def test_search_with_repo_filter(self, mock_httpx_client):
        """Test search with repository filter."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "total_matches": 0, "truncated": False}
        mock_httpx_client.request.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_httpx_client):
            client = LivegrepClient()
            client._client = mock_httpx_client

            client.search("test", repo_filter="my-project")

            call_args = mock_httpx_client.request.call_args
            query = call_args.kwargs.get("params", {}).get("q", "")
            assert "repo:my-project" in query

    def test_search_with_max_matches(self, mock_httpx_client):
        """Test search with max_matches limit."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "total_matches": 0, "truncated": False}
        mock_httpx_client.request.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_httpx_client):
            client = LivegrepClient()
            client._client = mock_httpx_client

            client.search("test", max_matches=25)

            call_args = mock_httpx_client.request.call_args
            query = call_args.kwargs.get("params", {}).get("q", "")
            assert "max_matches:25" in query

    def test_search_error_handling(self, mock_httpx_client):
        """Test search error handling."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_httpx_client.request.side_effect = Exception("Connection error")

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_httpx_client):
            client = LivegrepClient()
            client._client = mock_httpx_client

            response = client.search("test")

            assert len(response.results) == 0
            assert response.total_matches == 0

    def test_search_without_httpx(self, monkeypatch):
        """Test search when httpx is not available."""
        # Simulate httpx not being available
        with patch.dict('sys.modules', {'httpx': None}):
            from memory_mcp.livegrep_client import LivegrepClient

            client = LivegrepClient()
            response = client.search("test")

            assert len(response.results) == 0


class TestLivegrepClientSpecializedSearches:
    """Tests for specialized search methods."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LivegrepClient."""
        from memory_mcp.livegrep_client import LivegrepClient, LivegrepSearchResponse

        client = LivegrepClient()
        client.search = MagicMock(return_value=LivegrepSearchResponse(
            results=[],
            total_matches=0,
            truncated=False,
            query="",
            duration_ms=0
        ))
        return client

    def test_search_function_python(self, mock_client):
        """Test Python function search."""
        mock_client.search_function("my_function", language="python")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "def" in pattern
        assert "my_function" in pattern
        assert call_args.kwargs.get("path_filter") == "*.py"

    def test_search_function_javascript(self, mock_client):
        """Test JavaScript function search."""
        mock_client.search_function("myFunction", language="javascript")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "function" in pattern or "myFunction" in pattern
        assert call_args.kwargs.get("path_filter") == "*.js"

    def test_search_function_go(self, mock_client):
        """Test Go function search."""
        mock_client.search_function("MyFunc", language="go")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "func" in pattern
        assert "MyFunc" in pattern
        assert call_args.kwargs.get("path_filter") == "*.go"

    def test_search_class_python(self, mock_client):
        """Test Python class search."""
        mock_client.search_class("MyClass", language="python")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "class" in pattern
        assert "MyClass" in pattern
        assert call_args.kwargs.get("path_filter") == "*.py"

    def test_search_import_python(self, mock_client):
        """Test Python import search."""
        mock_client.search_import("numpy", language="python")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "import" in pattern or "from" in pattern
        assert "numpy" in pattern

    def test_search_string_literal(self, mock_client):
        """Test string literal search."""
        mock_client.search_string_literal("error message")

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "error message" in pattern or "error\\ message" in pattern

    def test_search_todo(self, mock_client):
        """Test TODO/FIXME search."""
        mock_client.search_todo()

        call_args = mock_client.search.call_args
        pattern = call_args.args[0]

        assert "TODO" in pattern or "FIXME" in pattern


class TestLivegrepClientHealthCheck:
    """Tests for health check functionality."""

    def test_health_check_success(self):
        """Test health check when server is available."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_client):
            client = LivegrepClient()
            client._client = mock_client

            assert client.health_check() is True

    def test_health_check_failure(self):
        """Test health check when server is unavailable."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_client):
            client = LivegrepClient()
            client._client = mock_client

            assert client.health_check() is False

    def test_health_check_without_httpx(self):
        """Test health check when httpx is not available."""
        from memory_mcp.livegrep_client import LivegrepClient

        client = LivegrepClient()
        # Force _client to None to simulate httpx not available
        client._client = None

        # Need to patch _get_client to return None
        with patch.object(client, '_get_client', return_value=None):
            assert client.health_check() is False


class TestLivegrepClientStats:
    """Tests for statistics functionality."""

    def test_get_stats_success(self):
        """Test getting stats when server is available."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "index_count": 5,
            "total_files": 10000
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_client):
            client = LivegrepClient()
            client._client = mock_client

            stats = client.get_stats()

            assert stats["available"] is True
            assert "endpoint" in stats

    def test_get_stats_without_httpx(self):
        """Test getting stats when httpx is not available."""
        from memory_mcp.livegrep_client import LivegrepClient

        client = LivegrepClient()

        with patch.object(client, '_get_client', return_value=None):
            stats = client.get_stats()

            assert stats["available"] is False
            assert "error" in stats


class TestLivegrepClientClose:
    """Tests for client cleanup."""

    def test_close_client(self):
        """Test closing the HTTP client."""
        from memory_mcp.livegrep_client import LivegrepClient, HTTPX_AVAILABLE

        if not HTTPX_AVAILABLE:
            pytest.skip("httpx not installed")

        mock_client = MagicMock()

        with patch('memory_mcp.livegrep_client.httpx.Client', return_value=mock_client):
            client = LivegrepClient()
            client._client = mock_client

            client.close()

            mock_client.close.assert_called_once()
            assert client._client is None
