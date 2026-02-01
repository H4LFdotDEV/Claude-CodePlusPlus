# handlers/__init__.py
# Handler package for Memory MCP Server
# Extracts tool implementations from server.py for better organization

from .base import BaseHandler
from .memory import MemoryHandler
from .session import SessionHandler
from .vault import VaultHandler
from .stats import StatsHandler
from .research import ResearchHandler
from .tier import TierHandler
from .proactive import ProactiveHandler
from .access import AccessHandler

__all__ = [
    "BaseHandler",
    "MemoryHandler",
    "SessionHandler",
    "VaultHandler",
    "StatsHandler",
    "ResearchHandler",
    "TierHandler",
    "ProactiveHandler",
    "AccessHandler",
]
