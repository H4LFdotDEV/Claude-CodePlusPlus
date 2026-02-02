# handlers/stats.py
# Statistics handler for memory system health and metrics

import time
import logging
from typing import Dict, Any

from .base import BaseHandler

logger = logging.getLogger("memory_mcp")


class StatsHandler(BaseHandler):
    """Handler for system statistics and health checks."""

    def get_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get system statistics with health checks.

        Args:
            args: Dict (currently unused, reserved for future filters)

        Returns:
            Dict containing:
            - sqlite_count: Total documents in cold storage
            - session_id: Current server session ID
            - components: Boolean availability of each component
            - health: Status and latency for each component
            - tiers: Multi-tier health and statistics
            - Detailed stats for sqlite, vault, redis, embedder
        """
        logger.debug("Gathering memory statistics")

        stats: Dict[str, Any] = {
            "sqlite_count": 0,
            "session_id": self._session_id,
            "components": {
                "sqlite": True,
                "vault": True,
                "redis": self.redis is not None,
                "embedder": self.embedder is not None,
                "tier_manager": self.tier_manager is not None
            },
            "health": {}
        }

        # SQLite stats with health check
        stats = self._check_sqlite_health(stats)

        # Vault stats with health check
        stats = self._check_vault_health(stats)

        # Redis stats with health check
        stats = self._check_redis_health(stats)

        # Embedder info with health check
        stats = self._check_embedder_health(stats)

        # Tier system stats
        stats = self._check_tier_health(stats)

        # Rate limiter stats
        stats = self._check_rate_limiter(stats)

        logger.debug(f"Stats gathered: {stats['sqlite_count']} documents in SQLite")
        return stats

    def _check_sqlite_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check SQLite health and gather stats."""
        try:
            start = time.time()
            sqlite_stats = self.sqlite.get_stats()
            latency_ms = (time.time() - start) * 1000
            return {
                **stats,
                "sqlite_count": sqlite_stats.get("total_documents", 0),
                "sqlite": sqlite_stats,
                "health": {
                    **stats["health"],
                    "sqlite": {
                        "status": "healthy",
                        "latency_ms": round(latency_ms, 2)
                    }
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get SQLite stats: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "sqlite": {"status": "error", "error": str(e)}
                }
            }

    def _check_vault_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check Vault health and gather stats."""
        try:
            start = time.time()
            vault_stats = self.vault.get_stats()
            latency_ms = (time.time() - start) * 1000
            return {
                **stats,
                "vault": vault_stats,
                "health": {
                    **stats["health"],
                    "vault": {
                        "status": "connected",
                        "latency_ms": round(latency_ms, 2)
                    }
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get vault stats: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "vault": {"status": "error", "error": str(e)}
                }
            }

    def _check_redis_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check Redis health and gather stats."""
        if not self.redis:
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "redis": {"status": "not_available"}
                }
            }

        try:
            start = time.time()
            redis_stats = self.redis.get_stats()
            health_ok = self.redis.health_check()
            latency_ms = (time.time() - start) * 1000
            return {
                **stats,
                "redis": redis_stats,
                "health": {
                    **stats["health"],
                    "redis": {
                        "status": "healthy" if health_ok else "degraded",
                        "latency_ms": round(latency_ms, 2)
                    }
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get Redis stats: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "redis": {"status": "error", "error": str(e)}
                }
            }

    def _check_embedder_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check embedder health."""
        if not self.embedder:
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "embedder": {"status": "not_available"}
                }
            }

        try:
            return {
                **stats,
                "embedder": {
                    "provider": self.embedder.name,
                    "dimension": getattr(self.embedder, 'dimension', None)
                },
                "health": {
                    **stats["health"],
                    "embedder": {"status": "active"}
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get embedder info: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "embedder": {"status": "error", "error": str(e)}
                }
            }

    def _check_tier_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check tier system health and gather tier-level statistics."""
        if not self.tier_manager:
            return {
                **stats,
                "tiers": {"status": "not_configured"}
            }

        try:
            start = time.time()
            tier_stats = self.tier_manager.get_tier_stats()
            latency_ms = (time.time() - start) * 1000

            # Add tier-level health indicators
            tier_health = {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2)
            }

            # Check each tier's availability
            tiers = tier_stats.get("tiers", {})
            available_tiers = [
                name for name, info in tiers.items()
                if info.get("available", False)
            ]
            tier_health["available_tiers"] = available_tiers

            return {
                **stats,
                "tiers": tier_stats,
                "health": {
                    **stats["health"],
                    "tier_manager": tier_health
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get tier stats: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "tier_manager": {"status": "error", "error": str(e)}
                }
            }

    def _check_rate_limiter(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check rate limiter status and gather stats."""
        if not self.rate_limiter:
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "rate_limiter": {"status": "not_configured"}
                }
            }

        try:
            rate_stats = self.rate_limiter.stats()
            client_status = self.rate_limiter.get_client_status(self._session_id)

            return {
                **stats,
                "rate_limiter": {
                    **rate_stats,
                    "current_session": {
                        "session_id": self._session_id,
                        "requests_in_window": client_status.current_count,
                        "limit": client_status.limit,
                        "allowed": client_status.allowed
                    }
                },
                "health": {
                    **stats["health"],
                    "rate_limiter": {"status": "active"}
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get rate limiter stats: {e}")
            return {
                **stats,
                "health": {
                    **stats["health"],
                    "rate_limiter": {"status": "error", "error": str(e)}
                }
            }
