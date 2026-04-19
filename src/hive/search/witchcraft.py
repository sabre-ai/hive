"""Witchcraft (Rust/T5) search backend — communicates via HTTP with hive-search."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from hive.search.base import SearchBackend
from hive.search.helpers import session_uuid

logger = logging.getLogger(__name__)


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


class WitchcraftBackend(SearchBackend):
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
        """Search via witchcraft and return ranked results."""
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
