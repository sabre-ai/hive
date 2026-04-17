"""Client for the witchcraft-powered hive-search server."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
    """Build a witchcraft document body from hive messages.

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
    """Build metadata JSON for a witchcraft document from a hive session."""
    return {
        "session_id": session.get("id", ""),
        "project_path": session.get("project_path", ""),
        "author": session.get("author", ""),
        "source": session.get("source", ""),
        "started_at": session.get("started_at", ""),
        "summary": session.get("summary", ""),
    }


def _build_filter(
    project: str | None = None,
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict | None:
    """Translate hive search filters to a witchcraft SqlStatementInternal JSON."""
    conditions: list[dict] = []

    if project:
        conditions.append(
            {
                "type": "Condition",
                "condition": {
                    "key": "$.project_path",
                    "operator": "Like",
                    "value": f"%{project}%",
                },
            }
        )
    if author:
        conditions.append(
            {
                "type": "Condition",
                "condition": {
                    "key": "$.author",
                    "operator": "Equals",
                    "value": author,
                },
            }
        )
    if since:
        conditions.append(
            {
                "type": "Condition",
                "condition": {
                    "key": "$.started_at",
                    "operator": "GreaterThanOrEquals",
                    "value": since,
                },
            }
        )
    if until:
        conditions.append(
            {
                "type": "Condition",
                "condition": {
                    "key": "$.started_at",
                    "operator": "LessThanOrEquals",
                    "value": until,
                },
            }
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {
        "type": "Group",
        "logic": "And",
        "statements": conditions,
    }


class SearchClient:
    """Sync HTTP client for the hive-search witchcraft server."""

    def __init__(self, base_url: str = "http://localhost:3033"):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Check if the search server is reachable."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=0.5)
            return r.status_code == 200
        except Exception:
            return False

    def add_document(
        self,
        session_id: str,
        date: str | None,
        metadata: dict[str, Any],
        body: str,
        chunk_lengths: list[int],
    ) -> None:
        """Add a document to the search index."""
        payload = {
            "uuid": session_uuid(session_id),
            "date": date,
            "metadata": json.dumps(metadata),
            "body": body,
            "chunk_lengths": chunk_lengths,
        }
        r = httpx.post(f"{self.base_url}/add", json=payload, timeout=5.0)
        r.raise_for_status()

    def remove_document(self, session_id: str) -> None:
        """Remove a document from the search index."""
        payload = {"uuid": session_uuid(session_id)}
        r = httpx.post(f"{self.base_url}/remove", json=payload, timeout=5.0)
        r.raise_for_status()

    def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search via witchcraft and return ranked results.

        Returns a list of dicts with keys: score, metadata (parsed), body, sub_idx, date.
        """
        payload: dict[str, Any] = {
            "query": query,
            "top_k": limit,
            "use_fulltext": True,
        }
        filt = _build_filter(project, author, since, until)
        if filt:
            payload["filter"] = filt

        r = httpx.post(f"{self.base_url}/search", json=payload, timeout=10.0)
        r.raise_for_status()
        results = r.json()

        # Parse metadata JSON string into dict for each result
        for item in results:
            try:
                item["metadata"] = json.loads(item["metadata"])
            except (json.JSONDecodeError, TypeError):
                item["metadata"] = {}

        return results

    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        """Tell the server to embed and index new documents."""
        payload: dict[str, Any] = {"limit": limit}
        r = httpx.post(f"{self.base_url}/index", json=payload, timeout=300.0)
        r.raise_for_status()
        return r.json()
