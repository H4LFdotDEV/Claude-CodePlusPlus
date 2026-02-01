# proactive/__init__.py
# Proactive Memory Module - memU-inspired continuous insight extraction
# Enables automatic learning without explicit user commands

from .extractor import InsightExtractor
from .insight_detector import InsightDetector, InsightType, Insight
from .queue_manager import ExtractionQueue, QueueItem

__all__ = [
    "InsightExtractor",
    "InsightDetector",
    "InsightType",
    "Insight",
    "ExtractionQueue",
    "QueueItem",
]
