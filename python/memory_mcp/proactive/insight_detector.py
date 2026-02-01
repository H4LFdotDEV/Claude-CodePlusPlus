# proactive/insight_detector.py
# Detect storeable insights from text using pattern matching and heuristics
# Inspired by memU's continuous learning without explicit commands

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger("memory_mcp.proactive")


class InsightType(Enum):
    """Types of insights that can be extracted from text."""
    PREFERENCE = "preference"      # User prefers X over Y
    DECISION = "decision"          # User decided to use X
    CORRECTION = "correction"      # User corrected previous info
    ERROR_SOLUTION = "error"       # Error message and its solution
    PATTERN = "pattern"            # Repeated behavior or workflow
    CONTEXT = "context"            # Background information
    RELATIONSHIP = "relationship"  # How concepts relate


@dataclass
class Insight:
    """An extracted insight from text."""
    type: InsightType
    content: str
    confidence: float  # 0.0 to 1.0
    source_text: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "type": self.type.value,
            "content": self.content,
            "confidence": self.confidence,
            "source_text": self.source_text[:500],  # Truncate for storage
            "tags": self.tags,
            "metadata": self.metadata,
            "extracted_at": self.extracted_at.isoformat(),
        }


class InsightDetector:
    """Detect insights from text using patterns and heuristics.

    Key memU-inspired behaviors:
    - Continuous extraction without explicit commands
    - Pattern detection across conversations
    - Confidence scoring for storage decisions
    """

    # Preference patterns
    PREFERENCE_PATTERNS = [
        (r"i (?:prefer|like|want|always use|usually use) (.+?)(?:\.|$)", 0.8),
        (r"(?:let's|we should) use (.+?) (?:for|instead|rather)", 0.7),
        (r"(.+?) is (?:better|preferred|my choice)", 0.7),
        (r"i (?:don't like|hate|avoid|never use) (.+?)(?:\.|$)", 0.8),
    ]

    # Decision patterns
    DECISION_PATTERNS = [
        (r"(?:we|i) decided (?:to|on) (.+?)(?:\.|$)", 0.9),
        (r"(?:the|our) decision (?:is|was) (.+?)(?:\.|$)", 0.9),
        (r"(?:let's|we'll) go with (.+?)(?:\.|$)", 0.8),
        (r"(?:chosen|chose|selected|picking) (.+?)(?:\.|$)", 0.8),
    ]

    # Correction patterns
    CORRECTION_PATTERNS = [
        (r"(?:actually|no|wait|correction),?\s+(.+?)(?:\.|$)", 0.85),
        (r"(?:i meant|i mean|that's wrong|not .+?, but) (.+?)(?:\.|$)", 0.85),
        (r"(?:changed my mind|forget what i said).+?(.+?)(?:\.|$)", 0.8),
        (r"(?:update|change) (?:that|this) to (.+?)(?:\.|$)", 0.8),
    ]

    # Error solution patterns
    ERROR_PATTERNS = [
        (r"(?:error|exception|failed|crash).+?(?:fixed|solved|resolved) by (.+?)(?:\.|$)", 0.9),
        (r"(?:the solution|the fix) (?:is|was) (.+?)(?:\.|$)", 0.9),
        (r"(?:solved|fixed|resolved) (?:it |this )?(?:by|with) (.+?)(?:\.|$)", 0.85),
    ]

    # Context/background patterns
    CONTEXT_PATTERNS = [
        (r"(?:for context|background|fyi|note that) (.+?)(?:\.|$)", 0.7),
        (r"(?:this project|this codebase|this repo) (?:is|uses|has) (.+?)(?:\.|$)", 0.75),
        (r"(?:we're|i'm) (?:using|working with|building) (.+?)(?:\.|$)", 0.7),
    ]

    # Minimum confidence to consider storing
    MIN_CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, min_confidence: float = 0.6):
        """Initialize detector with confidence threshold.

        Args:
            min_confidence: Minimum confidence score to accept an insight
        """
        self.min_confidence = max(0.0, min(1.0, min_confidence))
        self._pattern_cache: Dict[str, List[tuple]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        self._compiled = {
            InsightType.PREFERENCE: [
                (re.compile(p, re.IGNORECASE), c)
                for p, c in self.PREFERENCE_PATTERNS
            ],
            InsightType.DECISION: [
                (re.compile(p, re.IGNORECASE), c)
                for p, c in self.DECISION_PATTERNS
            ],
            InsightType.CORRECTION: [
                (re.compile(p, re.IGNORECASE), c)
                for p, c in self.CORRECTION_PATTERNS
            ],
            InsightType.ERROR_SOLUTION: [
                (re.compile(p, re.IGNORECASE), c)
                for p, c in self.ERROR_PATTERNS
            ],
            InsightType.CONTEXT: [
                (re.compile(p, re.IGNORECASE), c)
                for p, c in self.CONTEXT_PATTERNS
            ],
        }

    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Insight]:
        """Detect all insights from text.

        Args:
            text: Input text to analyze
            context: Optional context (project, session, etc.)

        Returns:
            List of detected insights above confidence threshold
        """
        if not text or not text.strip():
            return []

        insights: List[Insight] = []
        context = context or {}

        # Check each insight type
        for insight_type, patterns in self._compiled.items():
            for pattern, base_confidence in patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    content = match.group(1).strip() if match.groups() else match.group(0)
                    if not content or len(content) < 3:
                        continue

                    # Adjust confidence based on context
                    confidence = self._adjust_confidence(
                        base_confidence, content, insight_type, context
                    )

                    if confidence >= self.min_confidence:
                        insight = Insight(
                            type=insight_type,
                            content=content,
                            confidence=confidence,
                            source_text=text,
                            tags=self._generate_tags(insight_type, content, context),
                            metadata={
                                "pattern_match": pattern.pattern,
                                "project": context.get("project"),
                                "session_id": context.get("session_id"),
                            }
                        )
                        insights.append(insight)

        # Deduplicate similar insights
        return self._deduplicate(insights)

    def _adjust_confidence(
        self,
        base_confidence: float,
        content: str,
        insight_type: InsightType,
        context: Dict[str, Any]
    ) -> float:
        """Adjust confidence based on content quality and context.

        Args:
            base_confidence: Starting confidence from pattern match
            content: Extracted content
            insight_type: Type of insight
            context: Additional context

        Returns:
            Adjusted confidence score
        """
        confidence = base_confidence

        # Boost for longer, more specific content
        if len(content) > 50:
            confidence += 0.05
        elif len(content) < 10:
            confidence -= 0.1

        # Boost if project context matches
        if context.get("project") and context["project"].lower() in content.lower():
            confidence += 0.05

        # Penalty for vague content
        vague_words = ["something", "stuff", "thing", "whatever", "etc"]
        if any(word in content.lower() for word in vague_words):
            confidence -= 0.15

        # Boost for technical specificity
        technical_indicators = ["api", "function", "class", "method", "library", "framework"]
        if any(ind in content.lower() for ind in technical_indicators):
            confidence += 0.05

        return max(0.0, min(1.0, confidence))

    def _generate_tags(
        self,
        insight_type: InsightType,
        content: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate tags for the insight.

        Args:
            insight_type: Type of insight
            content: Insight content
            context: Additional context

        Returns:
            List of tags
        """
        tags = [f"insight:{insight_type.value}"]

        if context.get("project"):
            tags.append(f"project:{context['project']}")

        # Add technology tags based on content
        tech_patterns = {
            "typescript": ["typescript", "ts", ".tsx"],
            "python": ["python", "py", ".py"],
            "react": ["react", "jsx", "component"],
            "api": ["api", "endpoint", "rest", "graphql"],
            "database": ["database", "sql", "postgres", "mongo", "redis"],
        }

        content_lower = content.lower()
        for tech, indicators in tech_patterns.items():
            if any(ind in content_lower for ind in indicators):
                tags.append(f"tech:{tech}")
                break  # Only add first matching tech

        return tags

    def _deduplicate(self, insights: List[Insight]) -> List[Insight]:
        """Remove duplicate or overlapping insights.

        Args:
            insights: List of insights to deduplicate

        Returns:
            Deduplicated list, keeping highest confidence
        """
        if len(insights) <= 1:
            return insights

        # Group by content similarity
        seen: Dict[str, Insight] = {}
        for insight in insights:
            # Normalize content for comparison
            key = insight.content.lower().strip()[:50]

            if key not in seen or insight.confidence > seen[key].confidence:
                seen[key] = insight

        return list(seen.values())

    def should_store(self, insight: Insight, existing_count: int = 0) -> bool:
        """Determine if an insight should be stored.

        Considers:
        - Confidence threshold
        - Existing similar insights (avoid duplicates)
        - Content quality

        Args:
            insight: The insight to evaluate
            existing_count: Number of similar existing insights

        Returns:
            True if insight should be stored
        """
        # Must meet confidence threshold
        if insight.confidence < self.min_confidence:
            return False

        # Penalize if many similar insights exist
        if existing_count >= 3:
            # Require higher confidence for additional similar insights
            required = min(0.95, self.min_confidence + (existing_count * 0.1))
            if insight.confidence < required:
                return False

        # Content quality checks
        if len(insight.content) < 5:
            return False

        return True
