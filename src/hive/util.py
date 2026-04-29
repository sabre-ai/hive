"""Shared utilities for hive."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_repo_url(url: str) -> str | None:
    """Normalise a git remote URL to a canonical ``host/owner/repo`` string.

    Handles SSH (``git@host:owner/repo.git``), HTTPS, and ``ssh://`` formats.
    Returns *None* for unparseable input.

    >>> normalize_repo_url("git@github.com:acme/app.git")
    'github.com/acme/app'
    >>> normalize_repo_url("https://github.com/acme/app.git")
    'github.com/acme/app'
    """
    url = url.strip()
    if not url:
        return None

    # SSH shorthand: git@host:owner/repo.git
    m = re.match(r"^[\w.-]+@([\w.-]+):(.*)", url)
    if m:
        host = m.group(1).lower()
        path = m.group(2)
    else:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if not host:
            return None

    # Clean up path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")

    if not path:
        return None

    return f"{host}/{path}"
