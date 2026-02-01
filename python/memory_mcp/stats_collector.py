# stats_collector.py
# Lightweight statistics collector using file-based storage
# Replaces Prometheus/Grafana with simple file persistence
# Jeremiah Kroesche | Halfservers LLC

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("memory_mcp")


@dataclass
class TierStats:
    """Statistics for a single memory tier."""

    tier: str
    operation_count: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0
    last_updated: str = ""

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.operation_count == 0:
            return 0.0
        return self.total_latency_ms / self.operation_count


class StatsCollector:
    """Collects and persists memory tier statistics.

    Uses simple file-based storage for:
    - Zero additional infrastructure
    - Persistence across restarts
    - Human-readable output
    - Integration with hooks system
    """

    def __init__(self, stats_path: Optional[Path] = None):
        default_path = Path.home() / ".claude-code-pp" / "stats.json"
        self.stats_path = stats_path or default_path
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        self._stats: Dict[str, TierStats] = {}
        self._dirty = False
        self._load()

    def record_operation(
        self,
        tier: str,
        latency_ms: float,
        success: bool = True
    ) -> None:
        """Record a tier operation with latency.

        Args:
            tier: Name of the tier (redis, graphiti, sqlite, vault, livegrep)
            latency_ms: Operation latency in milliseconds
            success: Whether the operation succeeded
        """
        if tier not in self._stats:
            self._stats[tier] = TierStats(tier=tier)

        stats = self._stats[tier]
        stats.operation_count += 1
        stats.total_latency_ms += latency_ms
        if not success:
            stats.error_count += 1
        stats.last_updated = datetime.now(timezone.utc).isoformat()
        self._dirty = True

        # Batch saves to reduce I/O
        if stats.operation_count % 10 == 0:
            self._save()

    def get_stats(self) -> Dict[str, Dict]:
        """Get all tier statistics.

        Returns:
            Dict mapping tier names to their statistics
        """
        return {
            tier: {
                **asdict(stats),
                "avg_latency_ms": round(stats.avg_latency_ms, 2)
            }
            for tier, stats in self._stats.items()
        }

    def get_summary(self) -> str:
        """Get human-readable stats summary for hooks output.

        Returns:
            Formatted string with tier statistics
        """
        lines = ["Memory Tier Statistics:"]
        lines.append("-" * 50)

        for tier, stats in sorted(self._stats.items()):
            status = "✓" if stats.error_count == 0 else "⚠"
            lines.append(
                f"  {status} {tier:12} | "
                f"{stats.operation_count:6} ops | "
                f"avg {stats.avg_latency_ms:7.2f}ms | "
                f"{stats.error_count} errors"
            )

        if not self._stats:
            lines.append("  (no statistics recorded yet)")

        lines.append("-" * 50)
        return "\n".join(lines)

    def get_tier_health(self, tier: str) -> Dict:
        """Get health status for a specific tier.

        Args:
            tier: Name of the tier

        Returns:
            Dict with status, avg_latency_ms, error_rate
        """
        if tier not in self._stats:
            return {"status": "unknown", "operations": 0}

        stats = self._stats[tier]
        error_rate = (
            stats.error_count / stats.operation_count
            if stats.operation_count > 0 else 0
        )

        if error_rate > 0.5:
            status = "unhealthy"
        elif error_rate > 0.1:
            status = "degraded"
        elif stats.avg_latency_ms > 1000:
            status = "slow"
        else:
            status = "healthy"

        return {
            "status": status,
            "operations": stats.operation_count,
            "avg_latency_ms": round(stats.avg_latency_ms, 2),
            "error_rate": round(error_rate, 4),
            "last_updated": stats.last_updated
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._stats.clear()
        self._save()

    def flush(self) -> None:
        """Force save any pending statistics."""
        if self._dirty:
            self._save()

    def _load(self) -> None:
        """Load statistics from file."""
        if not self.stats_path.exists():
            return

        try:
            data = json.loads(self.stats_path.read_text())
            for tier, stats_dict in data.items():
                # Handle both old and new format
                if isinstance(stats_dict, dict):
                    self._stats[tier] = TierStats(**stats_dict)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to load stats: {e}")
            self._stats = {}

    def _save(self) -> None:
        """Save statistics to file."""
        try:
            data = {tier: asdict(stats) for tier, stats in self._stats.items()}
            self.stats_path.write_text(json.dumps(data, indent=2))
            self._dirty = False
        except Exception as e:
            logger.warning(f"Failed to save stats: {e}")


# Global instance
_collector: Optional[StatsCollector] = None


def get_collector() -> StatsCollector:
    """Get the global StatsCollector instance."""
    global _collector
    if _collector is None:
        _collector = StatsCollector()
    return _collector


def record(tier: str, latency_ms: float, success: bool = True) -> None:
    """Convenience function to record an operation.

    Args:
        tier: Name of the tier
        latency_ms: Operation latency in milliseconds
        success: Whether the operation succeeded
    """
    get_collector().record_operation(tier, latency_ms, success)
