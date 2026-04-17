"""Secret scrubbing for ingest pipeline."""

from __future__ import annotations

import re

from hive.config import Config


def scrub(text: str, config: Config | None = None) -> str:
    """Redact secrets from text using configured patterns."""
    if config is None:
        config = Config.load()
    for pattern in config.scrub_patterns:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def scrub_payload(payload: dict, config: Config | None = None) -> dict:
    """Deep-walk a session payload dict and scrub all string values."""
    if config is None:
        config = Config.load()
    return _scrub_dict(payload, config)


def _scrub_dict(obj, config):
    if isinstance(obj, dict):
        return {k: _scrub_dict(v, config) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_scrub_dict(item, config) for item in obj]
    elif isinstance(obj, str):
        return scrub(obj, config)
    return obj
