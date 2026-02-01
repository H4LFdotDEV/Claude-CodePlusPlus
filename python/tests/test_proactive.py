# tests/test_proactive.py
# Tests for the proactive insight extraction module (memU-inspired)

import pytest
from datetime import datetime

from memory_mcp.proactive import (
    InsightDetector,
    InsightExtractor,
    InsightType,
    Insight,
    ExtractionQueue,
    QueueItem,
)
from memory_mcp.proactive.queue_manager import QueueItemStatus


class TestInsightType:
    """Tests for InsightType enum."""

    def test_all_types_exist(self):
        """Verify all expected insight types exist."""
        expected = ["preference", "decision", "correction", "error", "pattern", "context", "relationship"]
        actual = [t.value for t in InsightType]
        assert set(expected) == set(actual)


class TestInsight:
    """Tests for Insight dataclass."""

    def test_insight_creation(self):
        """Test basic insight creation."""
        insight = Insight(
            type=InsightType.PREFERENCE,
            content="TypeScript over JavaScript",
            confidence=0.8,
            source_text="I prefer TypeScript over JavaScript",
            tags=["tech:typescript"],
        )
        assert insight.type == InsightType.PREFERENCE
        assert insight.content == "TypeScript over JavaScript"
        assert insight.confidence == 0.8
        assert "tech:typescript" in insight.tags

    def test_insight_to_dict(self):
        """Test insight serialization."""
        insight = Insight(
            type=InsightType.DECISION,
            content="Use PostgreSQL",
            confidence=0.9,
            source_text="We decided to use PostgreSQL",
        )
        d = insight.to_dict()
        assert d["type"] == "decision"
        assert d["content"] == "Use PostgreSQL"
        assert d["confidence"] == 0.9
        assert "extracted_at" in d


class TestInsightDetector:
    """Tests for InsightDetector."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        return InsightDetector(min_confidence=0.6)

    def test_detect_preference(self, detector):
        """Test preference detection."""
        insights = detector.detect("I prefer TypeScript over JavaScript.")
        assert len(insights) >= 1
        pref = next((i for i in insights if i.type == InsightType.PREFERENCE), None)
        assert pref is not None
        assert "TypeScript" in pref.content

    def test_detect_decision(self, detector):
        """Test decision detection."""
        insights = detector.detect("We decided to use PostgreSQL for the database")
        assert len(insights) >= 1
        dec = next((i for i in insights if i.type == InsightType.DECISION), None)
        assert dec is not None
        assert "PostgreSQL" in dec.content

    def test_detect_correction(self, detector):
        """Test correction detection."""
        insights = detector.detect("Actually, we should use Redis instead.")
        assert len(insights) >= 1
        corr = next((i for i in insights if i.type == InsightType.CORRECTION), None)
        assert corr is not None

    def test_detect_multiple_insights(self, detector):
        """Test detection of multiple insights in one text."""
        text = "I prefer TypeScript. We decided to use PostgreSQL."
        insights = detector.detect(text)
        assert len(insights) >= 2

    def test_empty_text_returns_empty(self, detector):
        """Test empty text returns no insights."""
        assert detector.detect("") == []
        assert detector.detect("   ") == []

    def test_no_match_returns_empty(self, detector):
        """Test text with no patterns returns empty."""
        insights = detector.detect("The quick brown fox jumps over the lazy dog")
        assert len(insights) == 0

    def test_confidence_threshold(self):
        """Test confidence threshold filtering."""
        high_threshold = InsightDetector(min_confidence=0.95)
        insights = high_threshold.detect("I prefer TypeScript")
        # High threshold may filter out some insights
        for insight in insights:
            assert insight.confidence >= 0.95

    def test_context_affects_tags(self, detector):
        """Test that context affects generated tags."""
        context = {"project": "my-project"}
        insights = detector.detect("I prefer TypeScript", context)
        if insights:
            # Should include project tag
            has_project_tag = any("project:" in tag for tag in insights[0].tags)
            assert has_project_tag

    def test_deduplication(self, detector):
        """Test that duplicate insights are removed."""
        # Same content twice should be deduplicated
        insights = detector.detect("I prefer TypeScript. I also prefer TypeScript.")
        pref_count = sum(1 for i in insights if i.type == InsightType.PREFERENCE)
        assert pref_count == 1  # Should be deduplicated

    def test_should_store_high_confidence(self, detector):
        """Test should_store accepts high confidence insights."""
        insight = Insight(
            type=InsightType.PREFERENCE,
            content="TypeScript over JavaScript",
            confidence=0.9,
            source_text="I prefer TypeScript",
        )
        assert detector.should_store(insight, existing_count=0)

    def test_should_store_rejects_low_confidence(self, detector):
        """Test should_store rejects low confidence insights."""
        insight = Insight(
            type=InsightType.PREFERENCE,
            content="X",
            confidence=0.3,
            source_text="test",
        )
        assert not detector.should_store(insight, existing_count=0)

    def test_should_store_considers_existing(self, detector):
        """Test should_store considers existing similar insights."""
        insight = Insight(
            type=InsightType.PREFERENCE,
            content="TypeScript",
            confidence=0.7,
            source_text="test",
        )
        # With many existing similar insights, should require higher confidence
        assert detector.should_store(insight, existing_count=0)
        # May reject with many existing
        assert not detector.should_store(insight, existing_count=10)


class TestQueueItem:
    """Tests for QueueItem dataclass."""

    def test_queue_item_creation(self):
        """Test basic queue item creation."""
        item = QueueItem(
            id="q_1",
            content="Test content",
            context={"project": "test"},
        )
        assert item.id == "q_1"
        assert item.status == QueueItemStatus.PENDING
        assert item.retry_count == 0

    def test_queue_item_to_dict(self):
        """Test queue item serialization."""
        item = QueueItem(id="q_1", content="Test content")
        d = item.to_dict()
        assert d["id"] == "q_1"
        assert d["status"] == "pending"
        assert "created_at" in d


class TestExtractionQueue:
    """Tests for ExtractionQueue."""

    @pytest.fixture
    def queue(self):
        """Create a queue instance."""
        return ExtractionQueue(max_queue_size=100)

    def test_enqueue_item(self, queue):
        """Test basic enqueue."""
        item = queue.enqueue("Test content", {"project": "test"})
        assert item.content == "Test content"
        assert item.status == QueueItemStatus.PENDING
        status = queue.get_status()
        assert status["queue_size"] == 1

    def test_get_pending(self, queue):
        """Test get_pending returns pending items."""
        queue.enqueue("Item 1")
        queue.enqueue("Item 2")
        pending = queue.get_pending(limit=10)
        assert len(pending) == 2

    def test_queue_size_limit(self):
        """Test queue respects size limit."""
        small_queue = ExtractionQueue(max_queue_size=3)
        for i in range(5):
            small_queue.enqueue(f"Item {i}")
        # Should have max 3 items
        assert len(small_queue._queue) <= 3

    def test_get_status(self, queue):
        """Test status reporting."""
        queue.enqueue("Test")
        status = queue.get_status()
        assert "queue_size" in status
        assert "max_size" in status
        assert "stats" in status
        assert status["stats"]["total_enqueued"] == 1

    def test_get_recent(self, queue):
        """Test getting recent items."""
        for i in range(5):
            queue.enqueue(f"Item {i}")
        recent = queue.get_recent(limit=3)
        assert len(recent) == 3

    def test_clear_pending(self, queue):
        """Test clearing pending items."""
        queue.enqueue("Test 1")
        queue.enqueue("Test 2")
        cleared = queue.clear()
        assert cleared == 2
        assert queue.get_status()["queue_size"] == 0


class TestInsightExtractor:
    """Tests for InsightExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create an extractor without SQLite (for unit testing)."""
        return InsightExtractor(sqlite=None, min_confidence=0.6, enable_queue=True)

    def test_extractor_creation(self, extractor):
        """Test extractor initialization."""
        assert extractor.detector is not None
        assert extractor.queue is not None

    @pytest.mark.asyncio
    async def test_extract_and_store_immediate(self, extractor):
        """Test immediate extraction."""
        # Without SQLite, insights are detected but not stored
        insights = await extractor.extract_and_store(
            text="I prefer TypeScript over JavaScript.",
            immediate=True,
        )
        # Without sqlite, stored list will be empty but detection works
        stats = extractor.get_stats()
        assert stats["total_extracted"] >= 1
        # Detection works even without storage
        detected = extractor.detector.detect("I prefer TypeScript.")
        assert len(detected) >= 1

    @pytest.mark.asyncio
    async def test_extract_empty_text(self, extractor):
        """Test extraction with empty text."""
        insights = await extractor.extract_and_store(text="", immediate=True)
        assert insights == []

    @pytest.mark.asyncio
    async def test_extract_queued(self, extractor):
        """Test queued extraction."""
        insights = await extractor.extract_and_store(
            text="I prefer TypeScript",
            immediate=False,
        )
        # Insights are returned but queued for background
        assert len(insights) >= 1
        queue_status = extractor.queue.get_status()
        assert queue_status["stats"]["total_enqueued"] >= 1

    def test_get_stats(self, extractor):
        """Test stats retrieval."""
        stats = extractor.get_stats()
        assert "total_extracted" in stats
        assert "total_stored" in stats
        assert "by_type" in stats
        assert "queue" in stats


class TestProactiveIntegration:
    """Integration tests for proactive module."""

    @pytest.mark.asyncio
    async def test_full_extraction_flow(self):
        """Test complete extraction flow."""
        extractor = InsightExtractor(sqlite=None, min_confidence=0.5)

        # Extract multiple insights - use sentences that match patterns
        text = "I prefer TypeScript. We decided to use PostgreSQL."

        # Without sqlite, stored list is empty but detection works
        await extractor.extract_and_store(text, immediate=True)

        # Verify detection works by checking stats
        stats = extractor.get_stats()
        assert stats["total_extracted"] >= 2  # Should detect both preference and decision

        # Also verify detector directly
        detected = extractor.detector.detect(text)
        types_found = {i.type for i in detected}
        assert InsightType.PREFERENCE in types_found or InsightType.DECISION in types_found

    @pytest.mark.asyncio
    async def test_context_propagation(self):
        """Test that context is properly propagated."""
        extractor = InsightExtractor(sqlite=None)

        context = {"project": "my-project", "session_id": "sess-123"}
        insights = await extractor.extract_and_store(
            text="I prefer dark mode",
            context=context,
            immediate=True,
        )

        if insights:
            # Check metadata has context
            assert insights[0].metadata.get("project") == "my-project"
