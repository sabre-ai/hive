"""Elasticsearch search backend (stub — not yet implemented)."""

from __future__ import annotations

from typing import Any

from hive.search.base import SearchBackend


class ElasticsearchBackend(SearchBackend):
    """Semantic search via Elasticsearch with dense vector fields.

    To implement, this backend would need:
    - ``url`` — Elasticsearch cluster URL
    - ``index_name`` — index for hive documents
    - ``embedding_model`` — model name for sentence embeddings
    - Uses Elasticsearch's ``dense_vector`` field type and ``knn`` search
    """

    def is_available(self) -> bool:
        raise NotImplementedError("elasticsearch backend is not yet implemented")

    def add_document(
        self,
        session_id: str,
        date: str | None,
        metadata: dict[str, Any],
        body: str,
        chunk_lengths: list[int],
    ) -> None:
        raise NotImplementedError("elasticsearch backend is not yet implemented")

    def remove_document(self, session_id: str) -> None:
        raise NotImplementedError("elasticsearch backend is not yet implemented")

    def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("elasticsearch backend is not yet implemented")

    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        raise NotImplementedError("elasticsearch backend is not yet implemented")
