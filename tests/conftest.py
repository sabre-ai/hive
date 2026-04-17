"""Shared fixtures for the hive test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive.config import Config
from hive.store.db import init_db
from hive.store.query import QueryAPI


@pytest.fixture()
def tmp_db(tmp_path: Path):
    """Create a temporary SQLite database, yield its path, and clean up."""
    db_path = tmp_path / "test_store.db"
    conn = init_db(db_path=db_path)
    conn.close()
    yield db_path
    # cleanup handled by tmp_path


@pytest.fixture()
def config(tmp_db: Path) -> Config:
    """Return a Config whose db_path points at the temporary database."""
    cfg = Config()
    cfg.db_path = tmp_db
    return cfg


@pytest.fixture()
def query_api(tmp_db: Path, config: Config) -> QueryAPI:
    """Return a QueryAPI wired to the temporary database."""
    return QueryAPI(config=config, db_path=tmp_db)


@pytest.fixture()
def sample_session() -> dict:
    """Return a dict matching the sessions table schema."""
    return {
        "id": "sess-001",
        "source": "claude-code",
        "project_path": "/home/dev/myproject",
        "author": "alice",
        "started_at": "2025-06-01T10:00:00",
        "ended_at": "2025-06-01T10:30:00",
        "message_count": 4,
        "summary": "Refactored the auth module",
    }


@pytest.fixture()
def sample_payload(sample_session: dict) -> dict:
    """Return a full export payload (session + messages + enrichments + edges)."""
    return {
        **sample_session,
        "messages": [
            {
                "session_id": sample_session["id"],
                "ordinal": 0,
                "role": "human",
                "content": "Please refactor the auth module",
                "tool_name": None,
                "timestamp": "2025-06-01T10:00:00",
            },
            {
                "session_id": sample_session["id"],
                "ordinal": 1,
                "role": "assistant",
                "content": "I will refactor src/auth.py to use dependency injection.",
                "tool_name": None,
                "timestamp": "2025-06-01T10:05:00",
            },
            {
                "session_id": sample_session["id"],
                "ordinal": 2,
                "role": "human",
                "content": "Looks good, also update the tests",
                "tool_name": None,
                "timestamp": "2025-06-01T10:10:00",
            },
            {
                "session_id": sample_session["id"],
                "ordinal": 3,
                "role": "assistant",
                "content": "Done. Updated tests/test_auth.py with new fixtures.",
                "tool_name": None,
                "timestamp": "2025-06-01T10:15:00",
            },
        ],
        "enrichments": [
            {
                "session_id": sample_session["id"],
                "source": "quality",
                "key": "message_count",
                "value": "4",
            },
            {
                "session_id": sample_session["id"],
                "source": "files",
                "key": "files_touched",
                "value": "src/auth.py,tests/test_auth.py",
            },
        ],
        "annotations": [],
        "edges": [
            {
                "source_type": "session",
                "source_id": sample_session["id"],
                "target_type": "file",
                "target_id": "src/auth.py",
                "relationship": "modified",
            },
            {
                "source_type": "session",
                "source_id": sample_session["id"],
                "target_type": "commit",
                "target_id": "abc123",
                "relationship": "produced",
            },
        ],
    }
