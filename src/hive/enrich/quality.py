"""Quality enricher — computes conversational quality metrics."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

# Phrases that suggest the human is correcting the assistant.
_CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bno\b", re.IGNORECASE),
    re.compile(r"\bactually\b", re.IGNORECASE),
    re.compile(r"\bthat'?s\s+wrong\b", re.IGNORECASE),
    re.compile(r"\binstead\b", re.IGNORECASE),
    re.compile(r"\bwait\b", re.IGNORECASE),
]


class QualityEnricher:
    """Produces lightweight quality signals from session messages."""

    def name(self) -> str:
        return "quality"

    def should_run(self, session: dict[str, Any]) -> bool:
        return True

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        messages: list[dict[str, Any]] = session.get("messages", [])
        results: dict[str, Any] = {}

        results["message_count"] = len(messages)

        human_count, assistant_count = self._role_counts(messages)
        results["human_assistant_ratio"] = (
            round(human_count / assistant_count, 3) if assistant_count > 0 else 0.0
        )

        results["correction_frequency"] = self._correction_frequency(messages, human_count)
        results["session_duration"] = self._session_duration(session)

        return results

    # ── Metrics ──────────────────────────────────────────────────────

    @staticmethod
    def _role_counts(messages: list[dict[str, Any]]) -> tuple[int, int]:
        human = sum(1 for m in messages if m.get("role") == "human")
        assistant = sum(1 for m in messages if m.get("role") == "assistant")
        return human, assistant

    @staticmethod
    def _correction_frequency(messages: list[dict[str, Any]], human_count: int) -> float:
        """Fraction of human messages that contain a correction signal."""
        if human_count == 0:
            return 0.0
        corrections = 0
        for msg in messages:
            if msg.get("role") != "human":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            if any(pat.search(content) for pat in _CORRECTION_PATTERNS):
                corrections += 1
        return round(corrections / human_count, 3)

    @staticmethod
    def _session_duration(session: dict[str, Any]) -> float:
        """Return session duration in seconds, or 0.0 if timestamps are missing."""
        started = session.get("started_at")
        ended = session.get("ended_at")
        if not started or not ended:
            return 0.0

        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]

        start_dt = _parse_datetime(started, formats)
        end_dt = _parse_datetime(ended, formats)

        if start_dt is None or end_dt is None:
            return 0.0

        delta = (end_dt - start_dt).total_seconds()
        return max(delta, 0.0)


def _parse_datetime(value: Any, formats: list[str]) -> datetime | None:
    """Try multiple datetime formats, returning *None* on failure."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    log.debug("Unable to parse datetime: %s", value)
    return None
