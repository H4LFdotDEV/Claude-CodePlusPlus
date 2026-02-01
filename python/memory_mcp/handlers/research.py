# handlers/research.py
# Research session handler for voice transcripts and whiteboard captures
# Jeremiah Kroesche | Halfservers LLC

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseHandler
from ..validation import validate_string, validate_list, validate_limit

logger = logging.getLogger("memory_mcp")


class ResearchHandler(BaseHandler):
    """Handler for research session operations.

    Provides tools for:
    - Starting/ending research sessions
    - Storing voice transcripts with speaker attribution
    - Storing whiteboard/webcam captures with descriptions
    - Searching across research data
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def session_start(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new research session.

        Args:
            arguments:
                name: Session name (required)
                focus_area: Research focus/topic (optional)
                participants: List of participant names (optional)

        Returns:
            Dict with session_id and metadata
        """
        name = validate_string(arguments.get("name"), "name", min_len=1, max_len=200)
        focus_area = arguments.get("focus_area", "")
        participants = validate_list(arguments.get("participants"), "participants", str)

        session_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        session_data = {
            "session_id": session_id,
            "name": name,
            "focus_area": focus_area,
            "participants": participants,
            "started_at": started_at,
            "transcripts": [],
            "captures": [],
            "insights": []
        }

        # Store in active sessions
        self._active_sessions[session_id] = session_data

        # Store session metadata in SQLite
        from ..sqlite_index import MemoryDocument
        doc = MemoryDocument(
            id=session_id,
            content=f"Research Session: {name}\nFocus: {focus_area}\nParticipants: {', '.join(participants)}",
            doc_type="research_session",
            source=f"research:{name}",
            tags=["research", "session", "active"],
            metadata={
                "name": name,
                "focus_area": focus_area,
                "participants": participants,
                "started_at": started_at,
                "status": "active"
            }
        )
        self.sqlite.upsert(doc)

        # Cache in Redis if available
        if self.redis:
            try:
                self.redis.set(
                    f"research:session:{session_id}",
                    json.dumps(session_data),
                    ex=86400  # 24h TTL
                )
                # Mark session as active
                self.redis.set(
                    "research:active_session",
                    session_id,
                    ex=86400
                )
            except Exception as e:
                logger.debug(f"Redis cache failed: {e}")

        # Create marker file for hooks
        try:
            import os
            marker_dir = os.path.expanduser("~/.claude-code-pp")
            os.makedirs(marker_dir, exist_ok=True)
            marker_path = os.path.join(marker_dir, "research_session_active")
            with open(marker_path, "w") as f:
                f.write(session_id)
        except Exception as e:
            logger.debug(f"Marker file creation failed: {e}")

        logger.info(f"Research session started: {name} ({session_id})")

        return {
            "content": [{"type": "text", "text": json.dumps({
                "session_id": session_id,
                "name": name,
                "focus_area": focus_area,
                "participants": participants,
                "started_at": started_at,
                "status": "active"
            }, indent=2)}]
        }

    def session_end(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """End a research session and generate summary.

        Args:
            arguments:
                session_id: Session to end (required)
                summary: Session summary (optional)
                action_items: List of action items (optional)
                key_decisions: List of key decisions (optional)

        Returns:
            Dict with session summary and vault path
        """
        session_id = validate_string(arguments.get("session_id"), "session_id")
        summary = arguments.get("summary", "")
        action_items = validate_list(arguments.get("action_items"), "action_items", str)
        key_decisions = validate_list(arguments.get("key_decisions"), "key_decisions", str)

        ended_at = datetime.now(timezone.utc).isoformat()

        # Get session data
        session_data = self._active_sessions.get(session_id)
        if not session_data:
            # Try to load from Redis or SQLite
            if self.redis:
                try:
                    cached = self.redis.get(f"research:session:{session_id}")
                    if cached:
                        session_data = json.loads(cached)
                except Exception:
                    pass

            if not session_data:
                doc = self.sqlite.get(session_id)
                if doc:
                    session_data = {
                        "session_id": session_id,
                        "name": doc.metadata.get("name", "Unknown"),
                        "focus_area": doc.metadata.get("focus_area", ""),
                        "participants": doc.metadata.get("participants", []),
                        "started_at": doc.metadata.get("started_at", ""),
                        "transcripts": [],
                        "captures": []
                    }

        if not session_data:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": f"Session not found: {session_id}"
                })}],
                "isError": True
            }

        # Update session data
        session_data["ended_at"] = ended_at
        session_data["summary"] = summary
        session_data["action_items"] = action_items
        session_data["key_decisions"] = key_decisions
        session_data["status"] = "completed"

        # Calculate duration
        try:
            start = datetime.fromisoformat(session_data["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            duration_minutes = int((end - start).total_seconds() / 60)
            session_data["duration_minutes"] = duration_minutes
        except Exception:
            duration_minutes = 0

        # Write to vault
        vault_path = self._write_session_to_vault(session_data)

        # Update SQLite
        doc = self.sqlite.get(session_id)
        if doc:
            updated_doc = MemoryDocument(
                id=doc.id,
                content=f"Research Session: {session_data['name']}\n\nSummary: {summary}\n\nAction Items:\n" +
                        "\n".join(f"- {item}" for item in action_items),
                doc_type="research_session",
                source=doc.source,
                tags=["research", "session", "completed"],
                metadata={
                    **doc.metadata,
                    "ended_at": ended_at,
                    "status": "completed",
                    "summary": summary,
                    "action_items": action_items,
                    "key_decisions": key_decisions,
                    "vault_path": vault_path,
                    "duration_minutes": duration_minutes
                }
            )
            self.sqlite.upsert(updated_doc)

        # Clean up Redis
        if self.redis:
            try:
                self.redis.delete(f"research:session:{session_id}")
                self.redis.delete("research:active_session")
            except Exception:
                pass

        # Remove from active sessions
        self._active_sessions.pop(session_id, None)

        # Remove marker file
        try:
            import os
            marker_path = os.path.expanduser("~/.claude-code-pp/research_session_active")
            if os.path.exists(marker_path):
                os.remove(marker_path)
        except Exception:
            pass

        logger.info(f"Research session ended: {session_data['name']} ({session_id})")

        return {
            "content": [{"type": "text", "text": json.dumps({
                "session_id": session_id,
                "name": session_data["name"],
                "status": "completed",
                "duration_minutes": duration_minutes,
                "transcript_count": len(session_data.get("transcripts", [])),
                "capture_count": len(session_data.get("captures", [])),
                "vault_path": vault_path
            }, indent=2)}]
        }

    def transcript_store(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Store a voice transcript segment.

        Args:
            arguments:
                text: Transcript text (required)
                speaker: Speaker name (optional, default "user")
                session_id: Associated session (optional)
                timestamp: Timestamp of segment (optional)

        Returns:
            Dict with transcript_id and storage confirmation
        """
        text = validate_string(arguments.get("text"), "text", min_len=1)
        speaker = arguments.get("speaker", "user")
        session_id = arguments.get("session_id")
        timestamp = arguments.get("timestamp", datetime.now(timezone.utc).isoformat())

        transcript_id = str(uuid.uuid4())

        # Store in SQLite
        from ..sqlite_index import MemoryDocument
        doc = MemoryDocument(
            id=transcript_id,
            content=f"[{speaker}]: {text}",
            doc_type="transcript",
            source=f"voice:{session_id or 'standalone'}:{timestamp}",
            tags=["transcript", "voice", f"speaker-{speaker.lower().replace(' ', '-')}"],
            metadata={
                "speaker": speaker,
                "session_id": session_id,
                "timestamp": timestamp,
                "word_count": len(text.split())
            }
        )
        self.sqlite.upsert(doc)

        # Add to active session if exists
        if session_id and session_id in self._active_sessions:
            self._active_sessions[session_id]["transcripts"].append({
                "id": transcript_id,
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp
            })

        # Cache recent transcript in Redis
        if self.redis and session_id:
            try:
                self.redis.lpush(
                    f"research:transcripts:{session_id}",
                    json.dumps({"id": transcript_id, "speaker": speaker, "text": text[:200]})
                )
                self.redis.ltrim(f"research:transcripts:{session_id}", 0, 99)  # Keep last 100
                self.redis.expire(f"research:transcripts:{session_id}", 86400)
            except Exception as e:
                logger.debug(f"Redis transcript cache failed: {e}")

        logger.info(f"Transcript stored: {transcript_id} (speaker: {speaker})")

        return {
            "content": [{"type": "text", "text": json.dumps({
                "transcript_id": transcript_id,
                "speaker": speaker,
                "session_id": session_id,
                "word_count": len(text.split()),
                "stored": True
            }, indent=2)}]
        }

    def capture_store(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Store a whiteboard/webcam capture.

        Args:
            arguments:
                description: Description of the capture (required)
                ocr_text: Extracted text from image (optional)
                image_path: Path to image file (optional)
                session_id: Associated session (optional)
                capture_type: Type of capture (whiteboard/webcam/screenshot)

        Returns:
            Dict with capture_id and storage confirmation
        """
        description = validate_string(arguments.get("description"), "description", min_len=1)
        ocr_text = arguments.get("ocr_text", "")
        image_path = arguments.get("image_path", "")
        session_id = arguments.get("session_id")
        capture_type = arguments.get("capture_type", "whiteboard")
        timestamp = datetime.now(timezone.utc).isoformat()

        capture_id = str(uuid.uuid4())

        # Build searchable content
        content_parts = [f"Capture: {description}"]
        if ocr_text:
            content_parts.append(f"OCR Text: {ocr_text}")
        content = "\n\n".join(content_parts)

        # Store in SQLite
        from ..sqlite_index import MemoryDocument
        doc = MemoryDocument(
            id=capture_id,
            content=content,
            doc_type="research_image",
            source=f"{capture_type}:{session_id or 'standalone'}:{timestamp}",
            tags=["capture", capture_type, "research"],
            metadata={
                "description": description,
                "ocr_text": ocr_text,
                "image_path": image_path,
                "session_id": session_id,
                "capture_type": capture_type,
                "timestamp": timestamp
            }
        )
        self.sqlite.upsert(doc)

        # Add to active session if exists
        if session_id and session_id in self._active_sessions:
            self._active_sessions[session_id]["captures"].append({
                "id": capture_id,
                "description": description,
                "ocr_text": ocr_text[:200] if ocr_text else "",
                "image_path": image_path,
                "timestamp": timestamp
            })

        # Write capture note to vault if session exists
        vault_path = ""
        if session_id:
            try:
                session_data = self._active_sessions.get(session_id, {})
                session_name = session_data.get("name", session_id)
                date_prefix = datetime.now().strftime("%Y-%m-%d")
                capture_num = len(session_data.get("captures", [])) if session_data else 1

                vault_note = self.vault.write_note(
                    path=f"research/{date_prefix}-{session_name}/captures/{capture_num:03d}-{capture_type}",
                    content=self._format_capture_note(description, ocr_text, image_path, timestamp),
                    frontmatter={
                        "type": "research_image",
                        "capture_type": capture_type,
                        "session_id": session_id,
                        "timestamp": timestamp
                    }
                )
                vault_path = vault_note.path if vault_note else ""
            except Exception as e:
                logger.debug(f"Vault write failed: {e}")

        logger.info(f"Capture stored: {capture_id} (type: {capture_type})")

        return {
            "content": [{"type": "text", "text": json.dumps({
                "capture_id": capture_id,
                "capture_type": capture_type,
                "session_id": session_id,
                "has_ocr": bool(ocr_text),
                "vault_path": vault_path,
                "stored": True
            }, indent=2)}]
        }

    def search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search across research data.

        Args:
            arguments:
                query: Search query (required)
                session_id: Filter to specific session (optional)
                type: Filter by type (transcript/research_image/research_session)
                limit: Maximum results (default 20)

        Returns:
            Dict with matching research items
        """
        query = validate_string(arguments.get("query"), "query", min_len=1)
        session_id = arguments.get("session_id")
        doc_type = arguments.get("type")
        limit = validate_limit(arguments.get("limit"), default=20)

        # Search SQLite
        results = self.sqlite.search_fulltext(query, limit=limit * 2)  # Over-fetch for filtering

        # Filter results
        filtered = []
        for doc in results:
            # Filter by research types
            if doc.doc_type not in ("transcript", "research_image", "research_session"):
                continue

            # Filter by specific type if provided
            if doc_type and doc.doc_type != doc_type:
                continue

            # Filter by session if provided
            if session_id and doc.metadata.get("session_id") != session_id:
                continue

            filtered.append({
                "id": doc.id,
                "type": doc.doc_type,
                "content": doc.content[:300],
                "source": doc.source,
                "session_id": doc.metadata.get("session_id"),
                "timestamp": doc.metadata.get("timestamp"),
                "speaker": doc.metadata.get("speaker") if doc.doc_type == "transcript" else None
            })

            if len(filtered) >= limit:
                break

        return {
            "content": [{"type": "text", "text": json.dumps({
                "query": query,
                "filters": {
                    "session_id": session_id,
                    "type": doc_type
                },
                "count": len(filtered),
                "results": filtered
            }, indent=2)}]
        }

    def _write_session_to_vault(self, session_data: Dict[str, Any]) -> str:
        """Write complete session to vault."""
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        session_name = session_data.get("name", "unnamed").replace(" ", "-").lower()
        base_path = f"research/{date_prefix}-{session_name}"

        # Write session overview
        session_content = self._format_session_note(session_data)
        vault_note = self.vault.write_note(
            path=f"{base_path}/session",
            content=session_content,
            frontmatter={
                "type": "research_session",
                "session_id": session_data["session_id"],
                "started_at": session_data.get("started_at"),
                "ended_at": session_data.get("ended_at"),
                "participants": session_data.get("participants", [])
            }
        )
        vault_path = vault_note.path if vault_note else ""

        # Write transcript if exists
        transcripts = session_data.get("transcripts", [])
        if transcripts:
            transcript_content = self._format_transcript_note(transcripts)
            self.vault.write_note(
                path=f"{base_path}/transcript",
                content=transcript_content,
                frontmatter={
                    "type": "transcript",
                    "session_id": session_data["session_id"],
                    "segment_count": len(transcripts)
                }
            )

        # Write insights if exists
        if session_data.get("action_items") or session_data.get("key_decisions"):
            insights_content = self._format_insights_note(session_data)
            self.vault.write_note(
                path=f"{base_path}/insights",
                content=insights_content,
                frontmatter={
                    "type": "research_session",
                    "session_id": session_data["session_id"]
                }
            )

        return vault_path

    def _format_session_note(self, session_data: Dict[str, Any]) -> str:
        """Format session data as markdown."""
        lines = [
            f"# {session_data.get('name', 'Research Session')}",
            "",
            f"**Focus:** {session_data.get('focus_area', 'General research')}",
            f"**Participants:** {', '.join(session_data.get('participants', ['Solo']))}",
            f"**Duration:** {session_data.get('duration_minutes', 0)} minutes",
            "",
            "## Summary",
            "",
            session_data.get("summary", "_No summary provided_"),
            "",
            "## Statistics",
            "",
            f"- Transcript segments: {len(session_data.get('transcripts', []))}",
            f"- Captures: {len(session_data.get('captures', []))}",
            "",
        ]
        return "\n".join(lines)

    def _format_transcript_note(self, transcripts: List[Dict]) -> str:
        """Format transcripts as markdown."""
        lines = ["# Session Transcript", ""]

        for t in transcripts:
            timestamp = t.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except Exception:
                    time_str = timestamp
            else:
                time_str = ""

            speaker = t.get("speaker", "Unknown")
            text = t.get("text", "")
            lines.append(f"**[{time_str}] {speaker}:** {text}")
            lines.append("")

        return "\n".join(lines)

    def _format_capture_note(
        self,
        description: str,
        ocr_text: str,
        image_path: str,
        timestamp: str
    ) -> str:
        """Format capture as markdown."""
        lines = [
            f"# Capture",
            "",
            f"**Captured:** {timestamp}",
            "",
            "## Description",
            "",
            description,
            "",
        ]

        if ocr_text:
            lines.extend([
                "## Extracted Text",
                "",
                "```",
                ocr_text,
                "```",
                "",
            ])

        if image_path:
            lines.extend([
                "## Image",
                "",
                f"![capture]({image_path})",
                "",
            ])

        return "\n".join(lines)

    def _format_insights_note(self, session_data: Dict[str, Any]) -> str:
        """Format insights as markdown."""
        lines = ["# Session Insights", ""]

        action_items = session_data.get("action_items", [])
        if action_items:
            lines.extend(["## Action Items", ""])
            for item in action_items:
                lines.append(f"- [ ] {item}")
            lines.append("")

        key_decisions = session_data.get("key_decisions", [])
        if key_decisions:
            lines.extend(["## Key Decisions", ""])
            for decision in key_decisions:
                lines.append(f"- {decision}")
            lines.append("")

        return "\n".join(lines)


# Import MemoryDocument for type hints
from ..sqlite_index import MemoryDocument
