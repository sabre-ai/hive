"""Files enricher — records file paths referenced during a session."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Heuristic pattern: absolute or project-relative paths that look like real files.
_FILE_PATH_RE = re.compile(
    r"""(?:^|[\s"'`(])"""  # boundary before the path
    r"""("""
    r"""(?:/[\w.\-]+)+"""  # absolute path  (/foo/bar.py)
    r"""|"""
    r"""(?:[\w.\-]+/)+[\w.\-]+"""  # relative path  (src/main.py)
    r""")""",
    re.MULTILINE,
)


class FilesEnricher:
    """Extracts file paths mentioned in session messages."""

    def name(self) -> str:
        return "files"

    def should_run(self, session: dict[str, Any]) -> bool:
        return True

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        paths: set[str] = set()
        messages: list[dict[str, Any]] = session.get("messages", [])

        for msg in messages:
            self._extract_from_tool_use(msg, paths)
            self._extract_from_content(msg, paths)

        if not paths:
            return {}

        sorted_paths = sorted(paths)
        return {"files_touched": ",".join(sorted_paths)}

    # ── Extraction strategies ────────────────────────────────────────

    @staticmethod
    def _extract_from_tool_use(msg: dict[str, Any], paths: set[str]) -> None:
        """Pull file paths from tool-use messages (e.g. Read, Edit, Write)."""
        content = msg.get("content", "")
        if not content:
            return

        # Tool messages often carry structured JSON with a file_path key.
        if msg.get("role") == "tool" or msg.get("tool_name"):
            try:
                data = json.loads(content) if isinstance(content, str) else content
                if isinstance(data, dict):
                    for key in ("file_path", "path", "filePath", "filename"):
                        val = data.get(key)
                        if isinstance(val, str) and val:
                            paths.add(val)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    @staticmethod
    def _extract_from_content(msg: dict[str, Any], paths: set[str]) -> None:
        """Fall back to regex extraction from free-text content."""
        content = msg.get("content")
        if not isinstance(content, str):
            return
        for match in _FILE_PATH_RE.finditer(content):
            candidate = match.group(1)
            # Filter out obviously non-path strings (URLs, version numbers, etc.)
            if candidate.startswith("http") or candidate.startswith("//"):
                continue
            paths.add(candidate)
