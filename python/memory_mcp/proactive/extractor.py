# proactive/extractor.py
# Main insight extraction orchestrator
# Combines detection, queuing, and storage for continuous learning

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import hashlib

from .insight_detector import InsightDetector, Insight, InsightType
from .queue_manager import ExtractionQueue, QueueItem

if TYPE_CHECKING:
    from ..sqlite_index import SQLiteIndex

logger = logging.getLogger("memory_mcp.proactive")


class InsightExtractor:
    """Orchestrates continuous insight extraction from text.

    Key memU-inspired behaviors:
    - Continuous extraction without explicit commands
    - Zero-delay queuing with async processing
    - Deduplication against existing memories
    - Confidence-based storage decisions
    """

    def __init__(
        self,
        sqlite: Optional["SQLiteIndex"] = None,
        min_confidence: float = 0.6,
        enable_queue: bool = True,
    ):
        """Initialize the extractor.

        Args:
            sqlite: SQLite index for deduplication checks
            min_confidence: Minimum confidence to store insights
            enable_queue: Whether to use background queue
        """
        self.sqlite = sqlite
        self.detector = InsightDetector(min_confidence=min_confidence)
        self.queue = ExtractionQueue() if enable_queue else None
        self._stats = {
            "total_extracted": 0,
            "total_stored": 0,
            "total_duplicates": 0,
            "by_type": {t.value: 0 for t in InsightType},
        }

        if self.queue:
            self.queue.set_processor(self._process_queue_items)

    async def extract_and_store(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        immediate: bool = False,
    ) -> List[Insight]:
        """Extract insights from text and store them.

        Args:
            text: Input text to analyze
            context: Optional context (project, session, etc.)
            immediate: If True, process immediately; if False, queue for background

        Returns:
            List of extracted insights (may not be stored yet if queued)
        """
        if not text or not text.strip():
            return []

        # Detect insights
        insights = self.detector.detect(text, context)
        self._stats["total_extracted"] += len(insights)

        for insight in insights:
            self._stats["by_type"][insight.type.value] += 1

        if not insights:
            return []

        if immediate or not self.queue:
            # Process immediately
            stored = await self._store_insights(insights, context)
            return stored
        else:
            # Queue for background processing
            self.queue.enqueue(text, context)
            return insights  # Return detected (not yet stored)

    async def _store_insights(
        self,
        insights: List[Insight],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Insight]:
        """Store insights after deduplication.

        Args:
            insights: Insights to potentially store
            context: Optional context

        Returns:
            List of actually stored insights
        """
        stored: List[Insight] = []
        context = context or {}

        for insight in insights:
            # Check for duplicates
            if await self._is_duplicate(insight):
                self._stats["total_duplicates"] += 1
                logger.debug(f"Skipping duplicate insight: {insight.content[:50]}")
                continue

            # Count existing similar insights
            existing_count = await self._count_similar(insight)

            # Decide whether to store
            if not self.detector.should_store(insight, existing_count):
                logger.debug(f"Skipping low-confidence insight: {insight.content[:50]}")
                continue

            # Store the insight
            if self.sqlite:
                try:
                    doc_id = self._generate_id(insight)
                    self.sqlite.add_document(
                        doc_id=doc_id,
                        content=insight.content,
                        doc_type=self._insight_type_to_doc_type(insight.type),
                        source=f"proactive:{insight.type.value}",
                        tags=insight.tags,
                        project=context.get("project"),
                        importance=self._confidence_to_importance(insight.confidence),
                    )
                    stored.append(insight)
                    self._stats["total_stored"] += 1
                    logger.info(
                        f"Stored {insight.type.value} insight: {insight.content[:50]}..."
                    )
                except Exception as e:
                    logger.error(f"Failed to store insight: {e}")

        return stored

    async def _process_queue_items(self, items: List[QueueItem]) -> None:
        """Process queued items (called by ExtractionQueue).

        Args:
            items: Queue items to process
        """
        for item in items:
            insights = self.detector.detect(item.content, item.context)
            if insights:
                stored = await self._store_insights(insights, item.context)
                item.result = {
                    "detected": len(insights),
                    "stored": len(stored),
                    "insights": [i.to_dict() for i in stored[:5]],  # Limit for storage
                }

    async def _is_duplicate(self, insight: Insight) -> bool:
        """Check if an insight is a duplicate of existing memory.

        Args:
            insight: Insight to check

        Returns:
            True if duplicate exists
        """
        if not self.sqlite:
            return False

        # Search for similar content
        try:
            results = self.sqlite.search(
                query=insight.content[:100],  # First 100 chars
                limit=5,
            )

            for result in results:
                # Check content similarity (simple substring match for now)
                existing_content = result.get("content", "").lower()
                insight_content = insight.content.lower()

                if insight_content in existing_content or existing_content in insight_content:
                    return True

                # Check hash similarity
                if self._content_hash(insight.content) == self._content_hash(result.get("content", "")):
                    return True

            return False

        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False

    async def _count_similar(self, insight: Insight) -> int:
        """Count similar existing insights.

        Args:
            insight: Insight to compare

        Returns:
            Count of similar existing insights
        """
        if not self.sqlite:
            return 0

        try:
            # Search with insight type tag
            results = self.sqlite.search(
                query=insight.content[:50],
                limit=10,
                filters={"tags": [f"insight:{insight.type.value}"]},
            )
            return len(results)
        except Exception:
            return 0

    def _generate_id(self, insight: Insight) -> str:
        """Generate a unique ID for an insight.

        Args:
            insight: The insight

        Returns:
            Unique document ID
        """
        content_hash = self._content_hash(insight.content)[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"insight_{insight.type.value}_{content_hash}_{timestamp}"

    def _content_hash(self, content: str) -> str:
        """Generate hash of content for deduplication.

        Args:
            content: Content to hash

        Returns:
            SHA256 hash
        """
        normalized = content.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _insight_type_to_doc_type(self, insight_type: InsightType) -> str:
        """Map insight type to document type.

        Args:
            insight_type: The insight type

        Returns:
            Document type string
        """
        mapping = {
            InsightType.PREFERENCE: "note",
            InsightType.DECISION: "note",
            InsightType.CORRECTION: "note",
            InsightType.ERROR_SOLUTION: "reference",
            InsightType.PATTERN: "note",
            InsightType.CONTEXT: "note",
            InsightType.RELATIONSHIP: "reference",
        }
        return mapping.get(insight_type, "note")

    def _confidence_to_importance(self, confidence: float) -> float:
        """Convert confidence score to importance (1-10 scale).

        Args:
            confidence: Confidence score (0.0-1.0)

        Returns:
            Importance score (1.0-10.0)
        """
        # Map 0.6-1.0 confidence to 5-10 importance
        # Below 0.6 shouldn't be stored anyway
        return max(5.0, min(10.0, 5.0 + (confidence * 5.0)))

    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics.

        Returns:
            Dictionary with extraction stats
        """
        stats = self._stats.copy()
        if self.queue:
            stats["queue"] = self.queue.get_status()
        return stats

    async def start_background_processing(self) -> None:
        """Start background queue processing."""
        if self.queue:
            await self.queue.start_processing()

    async def stop_background_processing(self) -> None:
        """Stop background queue processing."""
        if self.queue:
            await self.queue.stop_processing()
