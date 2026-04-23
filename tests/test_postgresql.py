"""Tests for PostgreSQL relational support.

These tests require a running PostgreSQL instance with pgvector.
Set HIVE_TEST_PG_URL to enable, e.g.:

    HIVE_TEST_PG_URL=postgresql://hive:hive@localhost:5432/hive pytest tests/test_postgresql.py -v
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("pg_query_api")
class TestPgUpsertAndGet:
    def test_upsert_and_get(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        result = pg_query_api.get_session(sample_session["id"])
        assert result is not None
        assert result["id"] == sample_session["id"]
        assert result["author"] == "alice"

    def test_get_missing_returns_none(self, pg_query_api):
        assert pg_query_api.get_session("nonexistent") is None


@pytest.mark.usefixtures("pg_query_api")
class TestPgListSessions:
    def test_list_all(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        results = pg_query_api.list_sessions()
        assert len(results) == 1
        assert results[0]["id"] == sample_session["id"]

    def test_filter_by_project(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        results = pg_query_api.list_sessions(project="myproject")
        assert len(results) == 1
        results = pg_query_api.list_sessions(project="nonexistent")
        assert len(results) == 0

    def test_filter_by_author(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        results = pg_query_api.list_sessions(author="alice")
        assert len(results) == 1
        results = pg_query_api.list_sessions(author="bob")
        assert len(results) == 0


@pytest.mark.usefixtures("pg_query_api")
class TestPgFTS:
    def test_tsvector_search(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        pg_query_api.index_session_fts(
            sample_session["id"], "refactor auth module dependency injection"
        )
        results = pg_query_api.search_sessions("refactor auth")
        assert len(results) >= 1
        assert results[0]["id"] == sample_session["id"]

    def test_search_no_results(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        pg_query_api.index_session_fts(sample_session["id"], "refactor auth module")
        results = pg_query_api.search_sessions("kubernetes deployment")
        assert len(results) == 0


@pytest.mark.usefixtures("pg_query_api")
class TestPgImportExport:
    def test_import_roundtrip(self, pg_query_api, sample_payload):
        pg_query_api.import_session(sample_payload)
        result = pg_query_api.get_session(sample_payload["id"], detail="messages")
        assert result is not None
        assert result["message_count"] == 4
        assert len(result["messages"]) == 4

    def test_import_idempotent(self, pg_query_api, sample_payload):
        pg_query_api.import_session(sample_payload)
        pg_query_api.import_session(sample_payload)
        result = pg_query_api.get_session(sample_payload["id"], detail="messages")
        assert result is not None
        assert len(result["messages"]) == 4


@pytest.mark.usefixtures("pg_query_api")
class TestPgDelete:
    def test_delete_cascades(self, pg_query_api, sample_payload):
        pg_query_api.import_session(sample_payload)
        assert pg_query_api.delete_session(sample_payload["id"]) is True
        assert pg_query_api.get_session(sample_payload["id"]) is None

    def test_delete_nonexistent(self, pg_query_api):
        assert pg_query_api.delete_session("nonexistent") is False


@pytest.mark.usefixtures("pg_query_api")
class TestPgLineage:
    def test_file_lineage(self, pg_query_api, sample_payload):
        pg_query_api.import_session(sample_payload)
        results = pg_query_api.get_lineage("src/auth.py", id_type="file")
        assert len(results) == 1
        assert results[0]["session_id"] == sample_payload["id"]
        # STRING_AGG should produce comma-separated values
        assert "modified" in results[0]["relationships"]


@pytest.mark.usefixtures("pg_query_api")
class TestPgStats:
    def test_flat_stats(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        stats = pg_query_api.get_stats()
        assert stats["total_sessions"] == 1

    def test_group_by_project(self, pg_query_api, sample_session):
        pg_query_api.upsert_session(sample_session)
        stats = pg_query_api.get_stats(group_by="project")
        assert len(stats) == 1
        assert stats[0]["total_sessions"] == 1
