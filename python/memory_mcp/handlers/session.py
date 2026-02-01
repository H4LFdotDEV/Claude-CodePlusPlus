# handlers/session.py
# Session management handler (save, restore)

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from .base import BaseHandler
from ..sqlite_index import MemoryDocument
from ..redis_client import SessionState
from ..validation import validate_string, validate_list

logger = logging.getLogger("memory_mcp")


class SessionHandler(BaseHandler):
    """Handler for session management operations."""

    def save(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Save session state.

        Args:
            args: Dict containing:
                - project_path (required): Path to current project
                - active_files (optional): List of active file paths
                - context (optional): Additional context dict

        Returns:
            Dict with session_id, saved status, and backend used
        """
        project_path = validate_string(args.get("project_path"), "project_path", min_len=1)
        active_files = validate_list(args.get("active_files"), "active_files", str)
        context = args.get("context", {}) or {}

        logger.debug(f"Saving session for project: {project_path}")

        if not self.redis:
            # Fallback: Store in SQLite as a session document
            logger.info("Redis not available - saving session to SQLite")
            doc = MemoryDocument(
                id=self._session_id,
                content=json.dumps({
                    "project_path": project_path,
                    "active_files": active_files,
                    "context": context
                }),
                doc_type="session",
                source=f"session:{project_path}",
                project=project_path
            )
            self.sqlite.insert(doc)
            return {"session_id": self._session_id, "saved": True, "backend": "sqlite"}

        # Use Redis (hot tier) for session storage
        session = SessionState(
            session_id=self._session_id,
            project_path=project_path,
            active_files=active_files,
            recent_queries=[],
            context_window=context.get("messages", []),
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )

        self.redis.save_session(session)
        logger.info(f"Session saved: {self._session_id}")
        return {"session_id": self._session_id, "saved": True, "backend": "redis"}

    def restore(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Restore session.

        Args:
            args: Dict containing:
                - session_id (optional): Specific session to restore;
                  if not provided, lists available sessions

        Returns:
            Dict with session details or available sessions list
        """
        session_id = args.get("session_id")

        if not self.redis:
            # Fallback: Restore from SQLite
            logger.info("Redis not available - restoring session from SQLite")
            if not session_id:
                # List available sessions
                docs = self.sqlite.search_by_type("session", limit=20)
                return {
                    "available_sessions": [{"id": d.id, "project": d.project} for d in docs],
                    "backend": "sqlite"
                }

            doc = self.sqlite.get(session_id)
            if not doc:
                return {"found": False, "session_id": session_id}

            try:
                session_data = json.loads(doc.content)
                self._session_id = session_id
                return {
                    "found": True,
                    "session_id": session_id,
                    "project_path": session_data.get("project_path"),
                    "active_files": session_data.get("active_files", []),
                    "restored": True,
                    "backend": "sqlite"
                }
            except json.JSONDecodeError:
                return {"found": False, "error": "Invalid session data"}

        logger.debug(f"Restoring session: {session_id or 'listing all'}")

        if not session_id:
            # List available sessions from Redis
            sessions = self.redis.list_sessions()
            return {"available_sessions": sessions, "backend": "redis"}

        session = self.redis.get_session(session_id)
        if not session:
            logger.debug(f"Session not found: {session_id}")
            return {"found": False, "session_id": session_id}

        self._session_id = session_id
        logger.info(f"Session restored: {session_id}")
        return {
            "found": True,
            "session_id": session.session_id,
            "project_path": session.project_path,
            "active_files": session.active_files,
            "restored": True,
            "backend": "redis"
        }
