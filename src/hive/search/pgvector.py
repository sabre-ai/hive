"""PostgreSQL pgvector search backend (stub — not yet implemented)."""

from __future__ import annotations

from typing import Any

from hive.search.base import SearchBackend


class PgvectorBackend(SearchBackend):
    """Semantic search via PostgreSQL with the pgvector extension.

    To implement, this backend would need:
    - ``dsn`` — PostgreSQL connection string
    - ``embedding_model`` — model name for sentence embeddings
    - Tables: ``documents`` (metadata + body), ``embeddings`` (vector column)
    - Uses ``pgvector``'s ``<=>`` cosine distance operator for KNN search
    """

    def is_available(self) -> bool:
        raise NotImplementedError("pgvector backend is not yet implemented")

    def add_document(
        self,
        session_id: str,
        date: str | None,
        metadata: dict[str, Any],
        body: str,
        chunk_lengths: list[int],
    ) -> None:
        raise NotImplementedError("pgvector backend is not yet implemented")

    def remove_document(self, session_id: str) -> None:
        raise NotImplementedError("pgvector backend is not yet implemented")

    def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("pgvector backend is not yet implemented")

    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        raise NotImplementedError("pgvector backend is not yet implemented")
