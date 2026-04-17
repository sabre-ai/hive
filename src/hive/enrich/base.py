"""Base protocol for enrichment plugins."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Enricher(Protocol):
    """Protocol that all enrichers must satisfy.

    Each enricher inspects a captured session dict and returns
    key-value pairs that are persisted as enrichment rows.
    """

    def name(self) -> str:
        """Unique identifier for this enricher (used as ``source`` in the DB)."""
        ...

    def should_run(self, session: dict[str, Any]) -> bool:
        """Return *True* when this enricher is applicable to *session*."""
        ...

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        """Execute the enrichment and return a mapping of key -> value pairs."""
        ...
