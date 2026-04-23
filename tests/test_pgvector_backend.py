"""Tests for the pgvector search backend.

Requires a running PostgreSQL instance with pgvector.
Set HIVE_TEST_PG_URL to enable, e.g.:

    HIVE_TEST_PG_URL=postgresql://hive:hive@localhost:5432/hive pytest tests/test_pgvector_backend.py -v
"""

from __future__ import annotations

import os

import pytest


def _cleanup_search_tables(dsn: str) -> None:
    """Drop search tables between tests."""
    try:
        import psycopg2

        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS search_chunks CASCADE")
        cur.execute("DROP TABLE IF EXISTS search_documents CASCADE")
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


@pytest.fixture()
def pgvector_backend():
    """Create a PgvectorBackend instance or skip if no PostgreSQL."""
    dsn = os.environ.get("HIVE_TEST_PG_URL")
    if not dsn:
        pytest.skip("Set HIVE_TEST_PG_URL to run pgvector tests")

    from hive.search.pgvector import PgvectorBackend

    _cleanup_search_tables(dsn)
    backend = PgvectorBackend(dsn=dsn, model_name="all-MiniLM-L6-v2")
    yield backend
    _cleanup_search_tables(dsn)


class TestPgvectorBackend:
    def test_is_available(self, pgvector_backend):
        assert pgvector_backend.is_available() is True

    def test_add_and_search_round_trip(self, pgvector_backend):
        pgvector_backend.add_document(
            session_id="pgv-001",
            date="2025-06-01",
            metadata={
                "session_id": "pgv-001",
                "project_path": "/home/dev/myproject",
                "author": "alice",
                "started_at": "2025-06-01T10:00:00",
            },
            body="Refactored the authentication module to use dependency injection",
            chunk_lengths=[],
        )
        result = pgvector_backend.trigger_index()
        assert result["embedded"] == 1

        results = pgvector_backend.search("auth refactor")
        assert len(results) >= 1
        assert results[0]["metadata"]["session_id"] == "pgv-001"

    def test_remove_document(self, pgvector_backend):
        pgvector_backend.add_document(
            session_id="pgv-002",
            date="2025-06-01",
            metadata={"session_id": "pgv-002"},
            body="This is a test document",
            chunk_lengths=[],
        )
        pgvector_backend.trigger_index()
        pgvector_backend.remove_document("pgv-002")

        results = pgvector_backend.search("test document")
        matching = [r for r in results if r["metadata"].get("session_id") == "pgv-002"]
        assert len(matching) == 0

    def test_trigger_index_no_pending(self, pgvector_backend):
        pgvector_backend._ensure_db()
        result = pgvector_backend.trigger_index()
        assert result["embedded"] == 0

    def test_filter_by_project(self, pgvector_backend):
        pgvector_backend.add_document(
            session_id="pgv-003",
            date="2025-06-01",
            metadata={
                "session_id": "pgv-003",
                "project_path": "/home/dev/frontend",
                "author": "bob",
            },
            body="Updated React components for the dashboard",
            chunk_lengths=[],
        )
        pgvector_backend.add_document(
            session_id="pgv-004",
            date="2025-06-01",
            metadata={
                "session_id": "pgv-004",
                "project_path": "/home/dev/backend",
                "author": "alice",
            },
            body="Updated API endpoints for the dashboard",
            chunk_lengths=[],
        )
        pgvector_backend.trigger_index()

        results = pgvector_backend.search("dashboard", project="frontend")
        session_ids = [r["metadata"]["session_id"] for r in results]
        assert "pgv-003" in session_ids
        assert "pgv-004" not in session_ids

    def test_filter_by_author(self, pgvector_backend):
        pgvector_backend.add_document(
            session_id="pgv-005",
            date="2025-06-01",
            metadata={"session_id": "pgv-005", "author": "alice"},
            body="Fixed login bug in production",
            chunk_lengths=[],
        )
        pgvector_backend.add_document(
            session_id="pgv-006",
            date="2025-06-01",
            metadata={"session_id": "pgv-006", "author": "bob"},
            body="Fixed login issue in staging",
            chunk_lengths=[],
        )
        pgvector_backend.trigger_index()

        results = pgvector_backend.search("login", author="alice")
        session_ids = [r["metadata"]["session_id"] for r in results]
        assert "pgv-005" in session_ids
        assert "pgv-006" not in session_ids
