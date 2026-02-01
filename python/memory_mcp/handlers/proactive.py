# handlers/proactive.py
# Handler for proactive insight extraction tools
# Implements memU-inspired continuous learning without explicit commands

import logging
import json
from typing import Dict, Any, Optional, TYPE_CHECKING

from .base import BaseHandler
from ..proactive import InsightExtractor
from ..async_utils import run_async

if TYPE_CHECKING:
    from ..sqlite_index import SQLiteIndex
    from ..vault_manager import VaultManager
    from ..redis_client import RedisClient
    from ..embedding_provider import FallbackEmbeddingProvider
    from ..tier_manager import TierManager

logger = logging.getLogger("memory_mcp.handlers.proactive")


class ProactiveHandler(BaseHandler):
    """Handler for proactive insight extraction tools.

    Provides:
    - proactive_status: Get extraction system status
    - extract_insights: Manually trigger extraction
    - configure_proactive: Adjust extraction settings
    """

    def __init__(
        self,
        sqlite: "SQLiteIndex",
        vault: "VaultManager",
        redis: Optional["RedisClient"] = None,
        embedder: Optional["FallbackEmbeddingProvider"] = None,
        tier_manager: Optional["TierManager"] = None,
        session_id: str = "",
    ):
        super().__init__(sqlite, vault, redis, embedder, tier_manager, session_id)
        self._extractor: Optional[InsightExtractor] = None
        self._enabled = True
        self._config = {
            "min_confidence": 0.6,
            "queue_enabled": True,
        }

    @property
    def extractor(self) -> InsightExtractor:
        """Lazy initialization of extractor."""
        if self._extractor is None:
            self._extractor = InsightExtractor(
                sqlite=self.sqlite,
                min_confidence=self._config["min_confidence"],
                enable_queue=self._config["queue_enabled"],
            )
        return self._extractor

    async def handle_proactive_status(
        self,
        include_recent: bool = True,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Get proactive extraction status.

        Args:
            include_recent: Include recent extracted insights
            limit: Max recent insights to return

        Returns:
            Status dictionary with stats and optionally recent insights
        """
        try:
            stats = self.extractor.get_stats()

            result = {
                "enabled": self._enabled,
                "config": self._config,
                "stats": stats,
            }

            if include_recent and self.extractor.queue:
                result["recent_items"] = self.extractor.queue.get_recent(limit)

            return result

        except Exception as e:
            logger.error(f"proactive_status failed: {e}")
            return {
                "error": str(e),
                "enabled": self._enabled,
                "config": self._config,
            }

    async def handle_extract_insights(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        immediate: bool = True,
    ) -> Dict[str, Any]:
        """Manually trigger insight extraction.

        Args:
            text: Text to extract insights from
            context: Optional context (project, session_id)
            immediate: Process immediately or queue for background

        Returns:
            Extraction results
        """
        if not self._enabled:
            return {
                "error": "Proactive extraction is disabled",
                "enabled": False,
            }

        if not text or not text.strip():
            return {
                "error": "Text is required",
                "extracted": 0,
            }

        try:
            # Add session_id to context if available
            ctx = context or {}
            if self.session_id and "session_id" not in ctx:
                ctx["session_id"] = self.session_id

            insights = await self.extractor.extract_and_store(
                text=text,
                context=ctx,
                immediate=immediate,
            )

            return {
                "extracted": len(insights),
                "immediate": immediate,
                "insights": [
                    {
                        "type": i.type.value,
                        "content": i.content,
                        "confidence": i.confidence,
                        "tags": i.tags,
                    }
                    for i in insights
                ],
            }

        except Exception as e:
            logger.error(f"extract_insights failed: {e}")
            return {
                "error": str(e),
                "extracted": 0,
            }

    async def handle_configure_proactive(
        self,
        min_confidence: Optional[float] = None,
        enabled: Optional[bool] = None,
        queue_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configure proactive extraction settings.

        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
            enabled: Enable/disable automatic extraction
            queue_enabled: Enable/disable background queue

        Returns:
            Updated configuration
        """
        changes = []

        if enabled is not None:
            self._enabled = enabled
            changes.append(f"enabled={enabled}")

        if min_confidence is not None:
            # Validate range
            min_confidence = max(0.0, min(1.0, min_confidence))
            self._config["min_confidence"] = min_confidence
            changes.append(f"min_confidence={min_confidence}")

            # Recreate extractor with new config
            self._extractor = None

        if queue_enabled is not None:
            self._config["queue_enabled"] = queue_enabled
            changes.append(f"queue_enabled={queue_enabled}")

            # Recreate extractor with new config
            self._extractor = None

        return {
            "success": True,
            "changes": changes,
            "config": {
                "enabled": self._enabled,
                **self._config,
            },
        }

    async def start_background_processing(self) -> None:
        """Start background queue processing."""
        if self._enabled and self._config["queue_enabled"]:
            await self.extractor.start_background_processing()
            logger.info("Started proactive background processing")

    async def stop_background_processing(self) -> None:
        """Stop background queue processing."""
        if self._extractor:
            await self._extractor.stop_background_processing()
            logger.info("Stopped proactive background processing")

    def extract_from_message(self, message: str, project: Optional[str] = None) -> None:
        """Hook to extract insights from incoming messages.

        Call this from the main server when processing user messages
        to enable continuous learning.

        Args:
            message: User message text
            project: Optional project context
        """
        if not self._enabled:
            return

        try:
            # Queue for background processing (non-blocking)
            self.extractor.queue.enqueue(
                content=message,
                context={
                    "project": project,
                    "session_id": self.session_id,
                    "source": "user_message",
                }
            )
        except Exception as e:
            logger.error(f"Failed to queue message for extraction: {e}")
