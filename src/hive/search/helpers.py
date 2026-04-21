"""Shared helpers used by all search backends."""

from __future__ import annotations

import re
import uuid
from typing import Any

# Deterministic namespace for session UUIDs
_HIVE_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Regex to strip fenced code blocks and inline code
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
# Strip XML-style system tags like <system-reminder>...</system-reminder>
_XML_TAG_RE = re.compile(r"<[a-z][\w-]*>[\s\S]*?</[a-z][\w-]*>", re.MULTILINE)


def session_uuid(session_id: str) -> str:
    """Deterministic UUID v5 from a session ID."""
    return str(uuid.uuid5(_HIVE_NS, session_id))


def sanitize(text: str) -> str:
    """Strip code blocks, inline code, and XML tags for better embeddings."""
    text = _CODE_BLOCK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _XML_TAG_RE.sub("", text)
    # Collapse whitespace runs
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_search_body(messages: list[dict[str, Any]]) -> tuple[str, list[int]]:
    """Build a search document body from hive messages.

    Returns (body_text, chunk_lengths) where chunk_lengths are character
    counts per message chunk.
    """
    parts: list[str] = []
    lengths: list[int] = []

    for msg in messages:
        content = msg.get("content")
        if not content:
            continue
        role = msg.get("role", "human")
        label = "[User]" if role == "human" else "[Assistant]"
        chunk = f"{label} {sanitize(content)}\n"
        parts.append(chunk)
        lengths.append(len(chunk))

    body = "".join(parts)
    return body, lengths


def build_metadata(session: dict[str, Any]) -> dict[str, Any]:
    """Build metadata dict for a search document from a hive session."""
    return {
        "session_id": session.get("id", ""),
        "project_path": session.get("project_path", ""),
        "author": session.get("author", ""),
        "source": session.get("source", ""),
        "started_at": session.get("started_at", ""),
        "summary": session.get("summary", ""),
    }
