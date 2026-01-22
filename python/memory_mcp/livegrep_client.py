# livegrep_client.py
# livegrep HTTP Client for Claude Code++ Memory System (Cold Tier)
# Jeremiah Kroesche | Halfservers LLC
#
# Provides fast regex code search across large codebases using livegrep.
# livegrep uses suffix array indexing for sub-100ms search across GBs of code.

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Check if httpx is available
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # For type hints
    logger.info("httpx not installed. Install with: pip install httpx")


@dataclass
class LivegrepResult:
    """A single search result from livegrep."""
    repo: str
    path: str
    line_number: int
    line_content: str
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "repo": self.repo,
            "path": self.path,
            "line": self.line_number,
            "content": self.line_content,
            "context_before": self.context_before,
            "context_after": self.context_after,
        }


@dataclass
class LivegrepSearchResponse:
    """Response from a livegrep search."""
    results: List[LivegrepResult]
    total_matches: int
    truncated: bool
    query: str
    duration_ms: float


class LivegrepClient:
    """
    HTTP client for livegrep code search with context manager support.

    livegrep provides:
    - Suffix array-based indexing for fast regex search
    - RE2 regex engine (guaranteed linear time)
    - Sub-100ms queries across GB-scale codebases
    - Filter operators: path:, repo:, -path:, -repo:, max_matches:

    Usage:
        # Context manager (recommended - ensures cleanup)
        with LivegrepClient() as client:
            results = client.search("def main")

        # Manual management
        client = LivegrepClient()
        try:
            results = client.search("def main")
        finally:
            client.close()

        # Search with filters
        results = client.search(
            "class.*Config",
            path_filter="*.py",
            repo_filter="my-project"
        )

        # Search for function definitions
        results = client.search_function("get_config", language="python")
    """

    # Retry settings
    MAX_RETRIES = 2
    RETRY_DELAY_BASE = 0.3  # seconds

    def __init__(
        self,
        endpoint: str = None,
        timeout: float = 30.0
    ):
        """
        Initialize livegrep client.

        Args:
            endpoint: livegrep HTTP endpoint (default: http://localhost:8910)
            timeout: Request timeout in seconds
        """
        self.endpoint = (endpoint or os.environ.get("LIVEGREP_ENDPOINT", "http://localhost:8910")).rstrip("/")
        self.timeout = timeout
        self._client: Optional["httpx.Client"] = None
        self._lock = threading.Lock()  # Thread safety for client creation

        if not HTTPX_AVAILABLE:
            logger.warning("httpx not available - livegrep search disabled")

    def __enter__(self) -> "LivegrepClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    def _get_client(self) -> Optional["httpx.Client"]:
        """Get or create HTTP client (thread-safe)."""
        if not HTTPX_AVAILABLE:
            return None

        # Double-checked locking for thread safety
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=self.timeout,
                        follow_redirects=True,
                    )
        return self._client

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Optional["httpx.Response"]:
        """
        Make HTTP request with retry logic for transient failures.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx

        Returns:
            Response object or None on failure
        """
        client = self._get_client()
        if not client:
            return None

        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = client.request(method, url, **kwargs)
                return response
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    logger.debug(f"Request timeout, retrying in {delay:.1f}s...")
                    time.sleep(delay)
            except httpx.ConnectError as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    logger.debug(f"Connection error, retrying in {delay:.1f}s...")
                    time.sleep(delay)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None

        if last_error:
            logger.warning(f"Request failed after {self.MAX_RETRIES + 1} attempts: {last_error}")
        return None

    def search(
        self,
        query: str,
        path_filter: Optional[str] = None,
        repo_filter: Optional[str] = None,
        exclude_path: Optional[str] = None,
        exclude_repo: Optional[str] = None,
        max_matches: int = 100,
        fold_case: str = "auto",
        context_lines: int = 0
    ) -> LivegrepSearchResponse:
        """
        Execute a code search query.
        
        Query syntax:
        - Regular expressions (RE2 syntax)
        - Special terms: path:, -path:, repo:, -repo:, max_matches:
        - Case-sensitive if query contains uppercase letters (by default)
        
        Args:
            query: RE2 regex pattern to search for
            path_filter: Include only files matching this glob (e.g., "*.py")
            repo_filter: Include only this repository
            exclude_path: Exclude files matching this pattern
            exclude_repo: Exclude this repository
            max_matches: Maximum number of results (default: 100)
            fold_case: Case handling - "auto", "yes", "no"
            context_lines: Lines of context to include (0 for none)
            
        Returns:
            LivegrepSearchResponse with results
        """
        client = self._get_client()
        if not client:
            return LivegrepSearchResponse(
                results=[],
                total_matches=0,
                truncated=False,
                query=query,
                duration_ms=0
            )

        # Build query with special terms
        full_query = query
        if path_filter:
            full_query = f"path:{path_filter} {full_query}"
        if repo_filter:
            full_query = f"repo:{repo_filter} {full_query}"
        if exclude_path:
            full_query = f"-path:{exclude_path} {full_query}"
        if exclude_repo:
            full_query = f"-repo:{exclude_repo} {full_query}"
        full_query = f"max_matches:{max_matches} {full_query}"

        start_time = time.time()

        # Use retry-enabled request
        response = self._request_with_retry(
            "GET",
            f"{self.endpoint}/api/v1/search/",
            params={
                "q": full_query,
                "fold_case": fold_case,
                "context": str(context_lines) if context_lines > 0 else None,
            }
        )

        duration_ms = (time.time() - start_time) * 1000

        if response is None:
            return LivegrepSearchResponse(
                results=[],
                total_matches=0,
                truncated=False,
                query=query,
                duration_ms=duration_ms
            )

        if response.status_code != 200:
            logger.warning(f"livegrep search returned {response.status_code}: {response.text[:200] if response.text else ''}")
            return LivegrepSearchResponse(
                results=[],
                total_matches=0,
                truncated=False,
                query=query,
                duration_ms=duration_ms
            )

        try:
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to parse livegrep response: {e}")
            return LivegrepSearchResponse(
                results=[],
                total_matches=0,
                truncated=False,
                query=query,
                duration_ms=duration_ms
            )

        # Parse results
        results = []
        for result in data.get("results", []):
            results.append(LivegrepResult(
                repo=result.get("tree", ""),
                path=result.get("path", ""),
                line_number=result.get("lno", 0),
                line_content=result.get("line", ""),
                context_before=result.get("context_before", []) or [],
                context_after=result.get("context_after", []) or [],
            ))

        if results:
            query_preview = query[:30] + "..." if len(query) > 30 else query
            logger.debug(f"livegrep search '{query_preview}': {len(results)} results in {duration_ms:.1f}ms")

        return LivegrepSearchResponse(
            results=results,
            total_matches=data.get("total_matches", len(results)),
            truncated=data.get("truncated", False),
            query=query,
            duration_ms=duration_ms
        )

    def search_function(
        self,
        function_name: str,
        language: Optional[str] = None,
        **kwargs
    ) -> LivegrepSearchResponse:
        """
        Search for function/method definitions.
        
        Args:
            function_name: Name of the function to find
            language: Programming language (python, javascript, go, rust, java, etc.)
            **kwargs: Additional arguments passed to search()
            
        Returns:
            LivegrepSearchResponse with results
        """
        # Escape special regex characters in function name
        escaped_name = re.escape(function_name)
        
        # Language-specific patterns for function definitions
        patterns = {
            "python": f"def\\s+{escaped_name}\\s*\\(",
            "javascript": f"(function\\s+{escaped_name}\\s*\\(|{escaped_name}\\s*[:=]\\s*(async\\s+)?function|{escaped_name}\\s*[:=]\\s*\\()",
            "typescript": f"(function\\s+{escaped_name}|{escaped_name}\\s*[:=]\\s*(async\\s+)?function|{escaped_name}\\s*[:=]\\s*\\(|{escaped_name}\\s*<.*>\\s*\\()",
            "go": f"func\\s+(\\(.*\\)\\s+)?{escaped_name}\\s*\\(",
            "rust": f"(fn|pub fn)\\s+{escaped_name}\\s*[<(]",
            "java": f"(public|private|protected|static|final|abstract)*\\s*\\w+\\s+{escaped_name}\\s*\\(",
            "c": f"\\w+\\s+{escaped_name}\\s*\\(",
            "cpp": f"\\w+\\s+{escaped_name}\\s*\\(",
        }
        
        # Default pattern matches common function definition styles
        pattern = patterns.get(language, f"(def|function|func|fn)\\s+{escaped_name}")
        
        # Set path filter based on language
        path_filters = {
            "python": "*.py",
            "javascript": "*.js",
            "typescript": "*.ts",
            "go": "*.go",
            "rust": "*.rs",
            "java": "*.java",
            "c": "*.[ch]",
            "cpp": "*.{cpp,cc,cxx,hpp,h}",
        }
        
        if language and "path_filter" not in kwargs:
            kwargs["path_filter"] = path_filters.get(language)
            
        return self.search(pattern, **kwargs)

    def search_class(
        self,
        class_name: str,
        language: Optional[str] = None,
        **kwargs
    ) -> LivegrepSearchResponse:
        """
        Search for class definitions.
        
        Args:
            class_name: Name of the class to find
            language: Programming language
            **kwargs: Additional arguments passed to search()
            
        Returns:
            LivegrepSearchResponse with results
        """
        escaped_name = re.escape(class_name)
        
        patterns = {
            "python": f"class\\s+{escaped_name}\\s*[:(]",
            "javascript": f"class\\s+{escaped_name}",
            "typescript": f"(class|interface)\\s+{escaped_name}",
            "go": f"type\\s+{escaped_name}\\s+struct",
            "rust": f"(struct|enum|trait)\\s+{escaped_name}",
            "java": f"(class|interface|enum)\\s+{escaped_name}",
        }
        
        pattern = patterns.get(language, f"class\\s+{escaped_name}")
        
        path_filters = {
            "python": "*.py",
            "javascript": "*.js",
            "typescript": "*.ts",
            "go": "*.go",
            "rust": "*.rs",
            "java": "*.java",
        }
        
        if language and "path_filter" not in kwargs:
            kwargs["path_filter"] = path_filters.get(language)
            
        return self.search(pattern, **kwargs)

    def search_import(
        self,
        module_name: str,
        language: Optional[str] = None,
        **kwargs
    ) -> LivegrepSearchResponse:
        """
        Search for import/require statements.
        
        Args:
            module_name: Name of the module being imported
            language: Programming language
            **kwargs: Additional arguments passed to search()
            
        Returns:
            LivegrepSearchResponse with results
        """
        escaped_name = re.escape(module_name)
        
        patterns = {
            "python": f"(from\\s+{escaped_name}\\s+import|import\\s+{escaped_name})",
            "javascript": f"(require\\(['\"].*{escaped_name}.*['\"]\\)|import\\s+.*from\\s+['\"].*{escaped_name})",
            "typescript": f"import\\s+.*from\\s+['\"].*{escaped_name}",
            "go": f"import\\s+.*[\"'].*{escaped_name}",
            "rust": f"use\\s+.*{escaped_name}",
            "java": f"import\\s+.*{escaped_name}",
        }
        
        pattern = patterns.get(language, f"(import|require|use).*{escaped_name}")
        return self.search(pattern, **kwargs)

    def search_string_literal(
        self,
        text: str,
        **kwargs
    ) -> LivegrepSearchResponse:
        """
        Search for string literals containing text.
        
        Args:
            text: Text to search for within strings
            **kwargs: Additional arguments passed to search()
            
        Returns:
            LivegrepSearchResponse with results
        """
        escaped_text = re.escape(text)
        # Match text within single or double quotes
        pattern = f'["\'].*{escaped_text}.*["\']'
        return self.search(pattern, **kwargs)

    def search_todo(
        self,
        **kwargs
    ) -> LivegrepSearchResponse:
        """
        Search for TODO, FIXME, HACK, XXX comments.
        
        Args:
            **kwargs: Additional arguments passed to search()
            
        Returns:
            LivegrepSearchResponse with results
        """
        pattern = r"(TODO|FIXME|HACK|XXX|BUG)(\s*:|\s*\(|\s+)"
        return self.search(pattern, **kwargs)

    def health_check(self) -> bool:
        """
        Check livegrep service availability.

        Returns:
            True if livegrep is responding, False otherwise
        """
        if not HTTPX_AVAILABLE:
            return False

        # Use a simple request without retry for health check
        client = self._get_client()
        if not client:
            return False

        try:
            # Send a simple query to test connectivity
            response = client.get(
                f"{self.endpoint}/api/v1/search/",
                params={"q": "test", "max_matches": "1"}
            )
            # Both 200 (success) and 400 (bad query but server up) indicate service is running
            return response.status_code in (200, 400)

        except Exception as e:
            logger.debug(f"livegrep health check failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get livegrep index statistics.

        Returns:
            Dict with index statistics
        """
        if not HTTPX_AVAILABLE:
            return {"available": False, "error": "httpx not installed"}

        response = self._request_with_retry("GET", f"{self.endpoint}/api/v1/stats/")

        if response is None:
            return {
                "available": False,
                "endpoint": self.endpoint,
                "error": "Failed to connect to livegrep"
            }

        if response.status_code == 200:
            try:
                return {
                    "available": True,
                    "endpoint": self.endpoint,
                    **response.json()
                }
            except Exception as e:
                return {
                    "available": True,
                    "endpoint": self.endpoint,
                    "error": f"Failed to parse stats: {e}"
                }
        else:
            return {
                "available": self.health_check(),
                "endpoint": self.endpoint,
                "error": f"Stats endpoint returned {response.status_code}"
            }

    def close(self):
        """Close the HTTP client (thread-safe)."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    logger.debug(f"Error closing livegrep client: {e}")
                finally:
                    self._client = None
