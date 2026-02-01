# handlers/tier.py
# Tier-specific operations for knowledge graph and code search
# Jeremiah Kroesche | Halfservers LLC

import logging
from typing import Dict, Any, Optional

from .base import BaseHandler
from ..validation import validate_string, validate_limit
from ..async_utils import run_async

logger = logging.getLogger("memory_mcp")

# Constants for search limits
MAX_ENTITY_SEARCH_LIMIT = 100
MAX_CODE_SEARCH_LIMIT = 200

# Timeout for async operations (seconds)
SEARCH_TIMEOUT_SECONDS = 30.0


def _validate_optional_string(
    value: Optional[str],
    field_name: str,
    max_len: int = 500
) -> Optional[str]:
    """Validate an optional string parameter."""
    if value is None:
        return None
    return validate_string(value, field_name, min_len=1, max_len=max_len)


class TierHandler(BaseHandler):
    """Handler for tier-specific operations (Graphiti knowledge graph, livegrep code search)."""

    def search_entities(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search Graphiti knowledge graph for entities.

        Args:
            args: Dict containing:
                - query (required): Search query
                - limit (optional): Max results (default 10, max 100)

        Returns:
            Dict with results list and total count
        """
        if not self.tier_manager or not self.tier_manager.graphiti:
            return {"error": "Knowledge graph not available", "results": [], "total": 0}

        query = validate_string(args.get("query"), "query", min_len=1, max_len=10000)
        limit = validate_limit(args.get("limit"), "limit", default=10)
        limit = min(limit, MAX_ENTITY_SEARCH_LIMIT)

        logger.debug(f"Searching entities for: '{query[:50]}...' limit={limit}")

        try:
            results = run_async(
                self.tier_manager.graphiti.search_entities(query, limit=limit),
                timeout=SEARCH_TIMEOUT_SECONDS
            )
            return {
                "results": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "summary": r.summary,
                        "labels": r.labels
                    }
                    for r in results
                ],
                "total": len(results)
            }
        except Exception as e:
            # Use warning for expected failures, not error
            logger.warning(f"Entity search failed: {e}")
            return {"error": str(e), "results": [], "total": 0}

    def search_facts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search Graphiti knowledge graph for facts/relationships.

        Args:
            args: Dict containing:
                - query (required): Search query
                - limit (optional): Max results (default 10, max 100)

        Returns:
            Dict with results list and total count
        """
        if not self.tier_manager or not self.tier_manager.graphiti:
            return {"error": "Knowledge graph not available", "results": [], "total": 0}

        query = validate_string(args.get("query"), "query", min_len=1, max_len=10000)
        limit = validate_limit(args.get("limit"), "limit", default=10)
        limit = min(limit, MAX_ENTITY_SEARCH_LIMIT)

        logger.debug(f"Searching facts for: '{query[:50]}...' limit={limit}")

        try:
            results = run_async(
                self.tier_manager.graphiti.search_facts(query, limit=limit),
                timeout=SEARCH_TIMEOUT_SECONDS
            )
            return {
                "results": [
                    {
                        "id": r.id,
                        "source": r.source_entity,
                        "target": r.target_entity,
                        "fact": r.fact,
                        "valid_at": r.valid_at,
                        "invalid_at": r.invalid_at
                    }
                    for r in results
                ],
                "total": len(results)
            }
        except Exception as e:
            logger.warning(f"Fact search failed: {e}")
            return {"error": str(e), "results": [], "total": 0}

    def code_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search code using livegrep.

        Args:
            args: Dict containing:
                - query (required): RE2 regex pattern
                - path_filter (optional): Glob pattern (e.g., '*.py')
                - repo_filter (optional): Repository name
                - limit (optional): Max results (default 50, max 200)

        Returns:
            Dict with results, total, truncated flag, and duration
        """
        if not self.tier_manager or not self.tier_manager.livegrep:
            return {"error": "Code search not available", "results": [], "total": 0}

        query = validate_string(args.get("query"), "query", min_len=1, max_len=10000)
        path_filter = _validate_optional_string(args.get("path_filter"), "path_filter", max_len=500)
        repo_filter = _validate_optional_string(args.get("repo_filter"), "repo_filter", max_len=200)
        limit = validate_limit(args.get("limit"), "limit", default=50)
        limit = min(limit, MAX_CODE_SEARCH_LIMIT)

        logger.debug(f"Code search for: '{query[:50]}...' limit={limit}")

        try:
            response = self.tier_manager.livegrep.search(
                query,
                path_filter=path_filter,
                repo_filter=repo_filter,
                max_matches=limit
            )

            return {
                "results": [r.to_dict() for r in response.results],
                "total": response.total_matches,
                "truncated": response.truncated,
                "duration_ms": response.duration_ms
            }
        except Exception as e:
            logger.warning(f"Code search failed: {e}")
            return {"error": str(e), "results": [], "total": 0}

    def search_function(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for function definitions.

        Args:
            args: Dict containing:
                - name (required): Function name
                - language (optional): Programming language (python, javascript, go, rust, java, etc.)
                - limit (optional): Max results (default 50, max 200)

        Returns:
            Dict with results and total count
        """
        if not self.tier_manager or not self.tier_manager.livegrep:
            return {"error": "Code search not available", "results": [], "total": 0}

        function_name = validate_string(args.get("name"), "name", min_len=1, max_len=200)
        language = _validate_optional_string(args.get("language"), "language", max_len=50)
        limit = validate_limit(args.get("limit"), "limit", default=50)
        limit = min(limit, MAX_CODE_SEARCH_LIMIT)

        logger.debug(f"Function search for: '{function_name}' language={language}")

        try:
            response = self.tier_manager.livegrep.search_function(
                function_name,
                language=language,
                max_matches=limit
            )

            return {
                "results": [r.to_dict() for r in response.results],
                "total": response.total_matches
            }
        except Exception as e:
            logger.warning(f"Function search failed: {e}")
            return {"error": str(e), "results": [], "total": 0}

    def search_class(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for class definitions.

        Args:
            args: Dict containing:
                - name (required): Class/struct name
                - language (optional): Programming language
                - limit (optional): Max results (default 50, max 200)

        Returns:
            Dict with results and total count
        """
        if not self.tier_manager or not self.tier_manager.livegrep:
            return {"error": "Code search not available", "results": [], "total": 0}

        class_name = validate_string(args.get("name"), "name", min_len=1, max_len=200)
        language = _validate_optional_string(args.get("language"), "language", max_len=50)
        limit = validate_limit(args.get("limit"), "limit", default=50)
        limit = min(limit, MAX_CODE_SEARCH_LIMIT)

        logger.debug(f"Class search for: '{class_name}' language={language}")

        try:
            response = self.tier_manager.livegrep.search_class(
                class_name,
                language=language,
                max_matches=limit
            )

            return {
                "results": [r.to_dict() for r in response.results],
                "total": response.total_matches
            }
        except Exception as e:
            logger.warning(f"Class search failed: {e}")
            return {"error": str(e), "results": [], "total": 0}
