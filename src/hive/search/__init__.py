"""Pluggable search backends for hive.

Re-exports shared helpers and the public API so existing ``from hive.search import …``
imports continue to work.
"""

from hive.search.base import SearchBackend
from hive.search.factory import get_search_backend
from hive.search.helpers import (
    build_metadata,
    build_search_body,
    sanitize,
    session_uuid,
)

# Backward compatibility: ``from hive.search import SearchClient``
from hive.search.witchcraft import WitchcraftBackend as SearchClient

__all__ = [
    "SearchBackend",
    "SearchClient",
    "build_metadata",
    "build_search_body",
    "get_search_backend",
    "sanitize",
    "session_uuid",
]
