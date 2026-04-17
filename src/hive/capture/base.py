"""Abstract base for capture adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CaptureAdapter(ABC):
    """Protocol that every capture adapter must satisfy.

    Each adapter translates events from a specific AI tool (Claude Code,
    Cursor, Copilot, etc.) into the shared hive storage schema.
    """

    @abstractmethod
    def name(self) -> str:
        """Return a short, stable identifier for this adapter (e.g. ``claude_code``)."""

    @abstractmethod
    def setup(self) -> None:
        """Perform any one-time initialisation such as installing hooks or
        creating watch directories.  Must be safe to call repeatedly
        (idempotent)."""

    @abstractmethod
    def handle(self, event_name: str, data: dict) -> None:
        """Process a single hook event.

        Parameters
        ----------
        event_name:
            Hook event type (e.g. ``SessionStart``, ``Stop``).
        data:
            Payload dict whose shape depends on *event_name*.  Adapters
            are expected to silently ignore events they do not recognise.
        """
