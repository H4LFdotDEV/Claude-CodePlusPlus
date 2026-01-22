#!/usr/bin/env python3
"""
Component Diagnostics for Memory MCP Server.

Provides comprehensive health checks and diagnostics for all Memory MCP components:
- SQLite (cold storage)
- Redis (hot cache)
- FAISS (vector search)
- Vault (archive storage)
- Embedder (embedding provider)

Usage:
    python -m memory_mcp.diagnostics

Output includes:
- Status for each component (OK, WARNING, ERROR)
- Detailed error messages
- Suggested fixes for common issues
"""

import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DiagnosticStatus(Enum):
    """Status levels for diagnostic checks."""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    NOT_AVAILABLE = "not_available"


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    component: str
    status: DiagnosticStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        return result


class Diagnostics:
    """Component diagnostics checker."""

    def __init__(self):
        self.results: List[DiagnosticResult] = []

    def check_all(self) -> List[DiagnosticResult]:
        """Run all diagnostic checks."""
        self.results = []

        # Check each component
        self.results.append(self._check_sqlite())
        self.results.append(self._check_vault())
        self.results.append(self._check_redis())
        self.results.append(self._check_faiss())
        self.results.append(self._check_embedder())

        return self.results

    def _check_sqlite(self) -> DiagnosticResult:
        """Check SQLite storage availability and health."""
        try:
            start = time.time()

            from .config import get_config
            from .sqlite_index import SQLiteIndex

            config = get_config()
            sqlite = SQLiteIndex()

            # Try to get stats
            stats = sqlite.get_stats()
            latency = (time.time() - start) * 1000

            return DiagnosticResult(
                component="SQLite",
                status=DiagnosticStatus.OK,
                message=f"Connected - {stats.get('total_documents', 0)} documents",
                details=stats,
                latency_ms=round(latency, 2)
            )

        except ImportError as e:
            return DiagnosticResult(
                component="SQLite",
                status=DiagnosticStatus.ERROR,
                message=f"Import error: {e}",
                suggestion="Ensure sqlite3 is installed (usually built-in with Python)"
            )
        except Exception as e:
            return DiagnosticResult(
                component="SQLite",
                status=DiagnosticStatus.ERROR,
                message=f"Connection failed: {e}",
                suggestion="Check SQLITE_PATH environment variable and file permissions"
            )

    def _check_vault(self) -> DiagnosticResult:
        """Check Obsidian vault availability."""
        try:
            start = time.time()

            from .config import get_config
            from .vault_manager import VaultManager

            config = get_config()
            vault = VaultManager()

            # Try to get stats
            stats = vault.get_stats()
            latency = (time.time() - start) * 1000

            vault_path = config.vault_path
            if not vault_path or not Path(vault_path).exists():
                return DiagnosticResult(
                    component="Vault",
                    status=DiagnosticStatus.WARNING,
                    message="Vault path not configured or doesn't exist",
                    suggestion="Set OBSIDIAN_VAULT_PATH environment variable to your vault directory",
                    details={"configured_path": vault_path}
                )

            return DiagnosticResult(
                component="Vault",
                status=DiagnosticStatus.OK,
                message=f"Connected to {vault_path}",
                details=stats,
                latency_ms=round(latency, 2)
            )

        except Exception as e:
            return DiagnosticResult(
                component="Vault",
                status=DiagnosticStatus.ERROR,
                message=f"Vault error: {e}",
                suggestion="Check OBSIDIAN_VAULT_PATH and ensure the directory exists"
            )

    def _check_redis(self) -> DiagnosticResult:
        """Check Redis availability and health."""
        try:
            from .redis_client import REDIS_AVAILABLE

            if not REDIS_AVAILABLE:
                return DiagnosticResult(
                    component="Redis",
                    status=DiagnosticStatus.NOT_AVAILABLE,
                    message="Redis client not installed",
                    suggestion="Install with: pip install redis"
                )

            start = time.time()
            from .redis_client import RedisClient

            client = RedisClient()
            if not client.connect():
                return DiagnosticResult(
                    component="Redis",
                    status=DiagnosticStatus.ERROR,
                    message="Failed to connect to Redis",
                    suggestion="Ensure Redis server is running: docker run -d -p 6379:6379 redis"
                )

            # Health check
            healthy = client.health_check()
            stats = client.get_stats()
            latency = (time.time() - start) * 1000

            if not healthy:
                return DiagnosticResult(
                    component="Redis",
                    status=DiagnosticStatus.WARNING,
                    message="Connected but health check failed",
                    details=stats,
                    latency_ms=round(latency, 2)
                )

            return DiagnosticResult(
                component="Redis",
                status=DiagnosticStatus.OK,
                message=f"Connected - {stats.get('used_memory', 'unknown')} memory used",
                details=stats,
                latency_ms=round(latency, 2)
            )

        except Exception as e:
            return DiagnosticResult(
                component="Redis",
                status=DiagnosticStatus.ERROR,
                message=f"Redis error: {e}",
                suggestion="Check REDIS_URL environment variable (default: redis://localhost:6379)"
            )

    def _check_faiss(self) -> DiagnosticResult:
        """Check FAISS availability and health."""
        try:
            from .faiss_manager import FAISS_AVAILABLE

            if not FAISS_AVAILABLE:
                return DiagnosticResult(
                    component="FAISS",
                    status=DiagnosticStatus.NOT_AVAILABLE,
                    message="FAISS library not installed",
                    suggestion="Install with: pip install faiss-cpu (or faiss-gpu for GPU support)"
                )

            start = time.time()
            from .faiss_manager import FAISSManager

            manager = FAISSManager()
            latency = (time.time() - start) * 1000

            return DiagnosticResult(
                component="FAISS",
                status=DiagnosticStatus.OK,
                message=f"Initialized - {manager.count} vectors, dimension={manager.dimension}",
                details={
                    "total_vectors": manager.count,
                    "dimension": manager.dimension,
                    "index_type": manager.config.index_type if hasattr(manager, 'config') else "unknown"
                },
                latency_ms=round(latency, 2)
            )

        except Exception as e:
            return DiagnosticResult(
                component="FAISS",
                status=DiagnosticStatus.ERROR,
                message=f"FAISS error: {e}",
                suggestion="Check FAISS_INDEX_PATH and ensure write permissions"
            )

    def _check_embedder(self) -> DiagnosticResult:
        """Check embedding provider availability."""
        try:
            start = time.time()
            from .embedding_provider import get_embedding_provider

            provider = get_embedding_provider()
            latency = (time.time() - start) * 1000

            if provider is None:
                return DiagnosticResult(
                    component="Embedder",
                    status=DiagnosticStatus.NOT_AVAILABLE,
                    message="No embedding provider configured",
                    suggestion="Install sentence-transformers or set VOYAGE_API_KEY for Voyage AI embeddings"
                )

            return DiagnosticResult(
                component="Embedder",
                status=DiagnosticStatus.OK,
                message=f"Using {provider.name}",
                details={
                    "provider": provider.name,
                    "dimension": getattr(provider, 'dimension', None)
                },
                latency_ms=round(latency, 2)
            )

        except Exception as e:
            return DiagnosticResult(
                component="Embedder",
                status=DiagnosticStatus.ERROR,
                message=f"Embedder error: {e}",
                suggestion="Check embedding provider installation and API keys"
            )

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all diagnostic results."""
        if not self.results:
            self.check_all()

        ok_count = sum(1 for r in self.results if r.status == DiagnosticStatus.OK)
        warning_count = sum(1 for r in self.results if r.status == DiagnosticStatus.WARNING)
        error_count = sum(1 for r in self.results if r.status == DiagnosticStatus.ERROR)
        not_available_count = sum(1 for r in self.results if r.status == DiagnosticStatus.NOT_AVAILABLE)

        # Core components are SQLite and Vault
        core_ok = all(
            r.status in (DiagnosticStatus.OK, DiagnosticStatus.WARNING)
            for r in self.results
            if r.component in ("SQLite", "Vault")
        )

        return {
            "total_checks": len(self.results),
            "ok": ok_count,
            "warnings": warning_count,
            "errors": error_count,
            "not_available": not_available_count,
            "core_healthy": core_ok,
            "results": [r.to_dict() for r in self.results]
        }


def print_diagnostics():
    """Print diagnostic results to console with formatting."""
    diag = Diagnostics()
    results = diag.check_all()

    print("\n" + "=" * 60)
    print("   Memory MCP Component Diagnostics")
    print("=" * 60 + "\n")

    # Status symbols
    symbols = {
        DiagnosticStatus.OK: "\033[92m✓\033[0m",
        DiagnosticStatus.WARNING: "\033[93m⚠\033[0m",
        DiagnosticStatus.ERROR: "\033[91m✗\033[0m",
        DiagnosticStatus.NOT_AVAILABLE: "\033[90m○\033[0m",
    }

    for result in results:
        symbol = symbols.get(result.status, "?")
        latency_str = f" ({result.latency_ms:.1f}ms)" if result.latency_ms else ""

        print(f"  {symbol} {result.component}: {result.message}{latency_str}")

        if result.suggestion:
            print(f"      \033[90m→ {result.suggestion}\033[0m")

        if result.details and result.status != DiagnosticStatus.OK:
            for key, value in result.details.items():
                print(f"      \033[90m{key}: {value}\033[0m")

    # Summary
    summary = diag.get_summary()
    print("\n" + "-" * 60)

    if summary["core_healthy"]:
        print("\033[92m  Core components healthy ✓\033[0m")
    else:
        print("\033[91m  Core components have issues ✗\033[0m")

    print(f"  Total: {summary['ok']} OK, {summary['warnings']} warnings, "
          f"{summary['errors']} errors, {summary['not_available']} not available")
    print()


def main():
    """Main entry point for CLI diagnostics."""
    print_diagnostics()


if __name__ == "__main__":
    main()
