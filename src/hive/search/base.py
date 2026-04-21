"""Abstract base class for search backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SearchBackend(ABC):
    """Interface that all search backends must implement."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is ready to accept queries."""
        ...

    @abstractmethod
    def add_document(
        self,
        session_id: str,
        date: str | None,
        metadata: dict[str, Any],
        body: str,
        chunk_lengths: list[int],
    ) -> None:
        """Add a document to the search index."""
        ...

    @abstractmethod
    def remove_document(self, session_id: str) -> None:
        """Remove a document from the search index."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search and return ranked results.

        Returns a list of dicts with keys: score, metadata (dict), body, sub_idx, date.
        """
        ...

    @abstractmethod
    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        """Embed and index any pending documents.

        Returns a dict with at least an 'embedded' key indicating count.
        """
        ...
