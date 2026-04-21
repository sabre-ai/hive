"""Capture adapter for Claude Desktop (Mac app) sessions.

Unlike ClaudeCodeAdapter, Claude Desktop has no hook system. Sessions are
captured via two paths:
  1. MCP bridge: Claude Desktop calls the ``capture_session`` MCP tool
  2. CLI import: ``hive import`` reads from file or stdin
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from hive.capture.base import CaptureAdapter
from hive.config import Config
from hive.privacy import scrub
from hive.store.db import init_db
from hive.store.query import QueryAPI


class ClaudeDesktopAdapter(CaptureAdapter):
    """Capture adapter for Claude Desktop conversations."""

    def __init__(self, config: Config | None = None):
        self._config = config or Config.load()
        init_db(self._config)
        self._api = QueryAPI(self._config)

    def name(self) -> str:
        return "claude_desktop"

    def setup(self) -> None:
        """No hooks to install — Claude Desktop uses MCP or manual import."""

    def handle(self, event_name: str, data: dict[str, Any]) -> None:
        if event_name in ("Import", "MCPCapture"):
            self._ingest(data)

    def _ingest(self, data: dict[str, Any]) -> None:
        """Ingest a session from either MCP capture or CLI import."""
        content = data.get("content", "")
        title = data.get("title", "")
        project = data.get("project")
        tags = data.get("tags", [])
        author = data.get("author")

        # Parse content into messages
        messages = self._parse_messages(content)
        if not messages and not title:
            return

        # Deterministic session ID from content hash (idempotent re-import)
        session_id = self._make_session_id(content or title)
        now = datetime.now(UTC).isoformat()

        # Build summary from title or first message
        summary = title or self._make_summary(messages)

        # Upsert session
        self._api.upsert_session(
            {
                "id": session_id,
                "source": self.name(),
                "project_path": project,
                "author": author,
                "started_at": now,
                "ended_at": now,
                "message_count": len(messages),
                "summary": summary,
            }
        )

        # Insert messages with scrubbing
        scrubbed_messages = []
        for i, msg in enumerate(messages):
            scrubbed_messages.append(
                {
                    "session_id": session_id,
                    "ordinal": i,
                    "role": msg["role"],
                    "content": scrub(msg["content"], self._config),
                    "timestamp": now,
                }
            )
        if scrubbed_messages:
            self._api.insert_messages(scrubbed_messages)

        # Index for full-text search
        fts_content = " ".join(m["content"] for m in scrubbed_messages if m["content"])
        if fts_content.strip():
            self._api.index_session_fts(session_id, fts_content)

        # Apply tags as annotations
        for tag in tags:
            self._api.write_annotation(session_id, "tag", tag)

        return session_id

    def _parse_messages(self, content: str) -> list[dict[str, str]]:
        """Parse content into structured messages.

        Accepts two formats:
        - Plain text with Human:/Assistant: markers
        - Already structured list of {role, content} dicts (passed through)
        """
        if not content or not content.strip():
            return []

        # Try JSON first (structured format)
        try:
            import json

            parsed = json.loads(content)
            if isinstance(parsed, list) and all(
                isinstance(m, dict) and "role" in m and "content" in m for m in parsed
            ):
                return [
                    {"role": self._normalize_role(m["role"]), "content": m["content"]}
                    for m in parsed
                ]
        except (json.JSONDecodeError, TypeError):
            pass

        # Parse plain text with role markers
        return self._parse_text_messages(content)

    def _parse_text_messages(self, text: str) -> list[dict[str, str]]:
        """Parse text with Human:/Assistant: role markers into messages."""
        # Split on role markers (Human:, Assistant:, User:, Claude:)
        pattern = r"^(Human|Assistant|User|Claude)\s*:\s*"
        parts = re.split(pattern, text, flags=re.MULTILINE)

        messages = []
        if len(parts) < 3:
            # No role markers found — treat entire text as a single human message
            return [{"role": "human", "content": text.strip()}]

        # parts[0] is text before first marker (usually empty), then alternating role/content
        i = 1  # skip preamble
        while i < len(parts) - 1:
            role_raw = parts[i].strip()
            content = parts[i + 1].strip()
            if content:
                messages.append({"role": self._normalize_role(role_raw), "content": content})
            i += 2

        return messages

    @staticmethod
    def _normalize_role(role: str) -> str:
        """Map various role names to the standard set."""
        role_lower = role.lower()
        if role_lower in ("human", "user"):
            return "human"
        if role_lower in ("assistant", "claude"):
            return "assistant"
        return "assistant"

    @staticmethod
    def _make_session_id(content: str) -> str:
        """Generate a deterministic UUID from content hash."""
        h = hashlib.sha256(content.encode()).digest()
        return str(uuid.UUID(bytes=h[:16], version=4))

    @staticmethod
    def _make_summary(messages: list[dict[str, str]]) -> str:
        """Generate a summary from the first human message."""
        for msg in messages:
            if msg["role"] == "human" and msg["content"]:
                text = msg["content"][:100]
                if len(msg["content"]) > 100:
                    text += "..."
                return text
        return "Claude Desktop session"
