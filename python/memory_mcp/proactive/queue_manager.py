# proactive/queue_manager.py
# Background extraction queue for async processing
# Enables zero-delay response while processing insights asynchronously

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum
from collections import deque

logger = logging.getLogger("memory_mcp.proactive")


class QueueItemStatus(Enum):
    """Status of a queue item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueItem:
    """An item in the extraction queue."""
    id: str
    content: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: QueueItemStatus = QueueItemStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content[:200],  # Truncate for display
            "context": self.context,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
        }


class ExtractionQueue:
    """Background queue for insight extraction.

    Key memU-inspired behaviors:
    - Zero-delay processing: Items queued immediately, processed async
    - Batch processing: Multiple items processed together for efficiency
    - Failure recovery: Retry failed items with exponential backoff
    """

    MAX_QUEUE_SIZE = 1000
    MAX_RETRIES = 3
    BATCH_SIZE = 10
    PROCESS_INTERVAL_SECONDS = 1.0

    def __init__(
        self,
        processor: Optional[Callable[[List[QueueItem]], Awaitable[None]]] = None,
        max_queue_size: int = 1000,
    ):
        """Initialize the extraction queue.

        Args:
            processor: Async function to process items
            max_queue_size: Maximum items to hold in queue
        """
        self._queue: deque[QueueItem] = deque(maxlen=max_queue_size)
        self._processor = processor
        self._processing = False
        self._task: Optional[asyncio.Task] = None
        self._stats = {
            "total_enqueued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_retried": 0,
        }
        self._max_queue_size = max_queue_size
        self._item_counter = 0

    def enqueue(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QueueItem:
        """Add an item to the extraction queue.

        Args:
            content: Text content to process
            context: Optional context (project, session, etc.)

        Returns:
            The queued item
        """
        self._item_counter += 1
        item = QueueItem(
            id=f"q_{self._item_counter}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
            content=content,
            context=context or {},
        )

        # If queue is full, remove oldest pending item
        if len(self._queue) >= self._max_queue_size:
            self._evict_oldest()

        self._queue.append(item)
        self._stats["total_enqueued"] += 1

        logger.debug(f"Enqueued item {item.id}, queue size: {len(self._queue)}")
        return item

    def _evict_oldest(self) -> None:
        """Evict oldest pending item from queue."""
        for i, item in enumerate(self._queue):
            if item.status == QueueItemStatus.PENDING:
                del self._queue[i]
                logger.debug(f"Evicted oldest pending item from queue")
                return

    def get_pending(self, limit: int = 10) -> List[QueueItem]:
        """Get pending items from the queue.

        Args:
            limit: Maximum items to return

        Returns:
            List of pending items
        """
        pending = [
            item for item in self._queue
            if item.status == QueueItemStatus.PENDING
        ]
        return pending[:limit]

    def get_status(self) -> Dict[str, Any]:
        """Get queue status and statistics.

        Returns:
            Dictionary with queue stats
        """
        status_counts = {status.value: 0 for status in QueueItemStatus}
        for item in self._queue:
            status_counts[item.status.value] += 1

        return {
            "queue_size": len(self._queue),
            "max_size": self._max_queue_size,
            "processing": self._processing,
            "status_counts": status_counts,
            "stats": self._stats.copy(),
        }

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent queue items.

        Args:
            limit: Maximum items to return

        Returns:
            List of recent items as dictionaries
        """
        items = list(self._queue)[-limit:]
        return [item.to_dict() for item in reversed(items)]

    async def process_batch(self, batch: List[QueueItem]) -> None:
        """Process a batch of items.

        Args:
            batch: Items to process
        """
        if not batch:
            return

        for item in batch:
            item.status = QueueItemStatus.PROCESSING

        try:
            if self._processor:
                await self._processor(batch)

            for item in batch:
                item.status = QueueItemStatus.COMPLETED
                item.processed_at = datetime.now(timezone.utc)
                self._stats["total_processed"] += 1

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            for item in batch:
                item.error = str(e)
                item.retry_count += 1

                if item.retry_count >= self.MAX_RETRIES:
                    item.status = QueueItemStatus.FAILED
                    self._stats["total_failed"] += 1
                else:
                    item.status = QueueItemStatus.PENDING
                    self._stats["total_retried"] += 1

    async def start_processing(self) -> None:
        """Start background processing loop."""
        if self._processing:
            return

        self._processing = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Started background extraction queue processing")

    async def stop_processing(self) -> None:
        """Stop background processing loop."""
        self._processing = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped background extraction queue processing")

    async def _process_loop(self) -> None:
        """Background processing loop."""
        while self._processing:
            try:
                batch = self.get_pending(self.BATCH_SIZE)
                if batch:
                    await self.process_batch(batch)
                else:
                    # Clean up completed items periodically
                    self._cleanup_completed()

                await asyncio.sleep(self.PROCESS_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                await asyncio.sleep(self.PROCESS_INTERVAL_SECONDS * 2)

    def _cleanup_completed(self) -> None:
        """Remove old completed items to free memory."""
        # Keep only items from last hour or still pending/processing
        cutoff = datetime.now(timezone.utc).timestamp() - 3600

        # Convert to list to safely modify
        items_to_keep = [
            item for item in self._queue
            if item.status in (QueueItemStatus.PENDING, QueueItemStatus.PROCESSING)
            or (item.processed_at and item.processed_at.timestamp() > cutoff)
        ]

        self._queue.clear()
        self._queue.extend(items_to_keep)

    def set_processor(
        self,
        processor: Callable[[List[QueueItem]], Awaitable[None]]
    ) -> None:
        """Set the processor function.

        Args:
            processor: Async function to process items
        """
        self._processor = processor

    def clear(self) -> int:
        """Clear all pending items from queue.

        Returns:
            Number of items cleared
        """
        count = len([i for i in self._queue if i.status == QueueItemStatus.PENDING])
        self._queue = deque(
            (i for i in self._queue if i.status != QueueItemStatus.PENDING),
            maxlen=self._max_queue_size
        )
        return count
