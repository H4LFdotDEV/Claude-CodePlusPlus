"""Shared utilities for Claude Code++.

General-purpose utilities that can be used by any component,
not specific to Memory MCP.
"""

from .cost_tracker import CostTracker, MODEL_PRICING, BudgetExceededError
from .embedding_cache import UnifiedEmbeddingCache
from .llm_cache import LLMResponseCache
from .log_utils import log_safe_query, log_safe_text, sanitize_log_data
from .model_router import ModelRouter, TaskComplexity, ModelConfig

__all__ = [
    "CostTracker",
    "MODEL_PRICING",
    "BudgetExceededError",
    "UnifiedEmbeddingCache",
    "LLMResponseCache",
    "log_safe_query",
    "log_safe_text",
    "sanitize_log_data",
    "ModelRouter",
    "TaskComplexity",
    "ModelConfig",
]
