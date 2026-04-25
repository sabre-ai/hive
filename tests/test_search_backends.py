"""Tests for the pluggable search backend system."""

from __future__ import annotations

import pytest

from hive.config import Config
from hive.search.base import SearchBackend
from hive.search.factory import get_search_backend
from hive.search.helpers import build_metadata, build_search_body, sanitize, session_uuid
from hive.search.witchcraft import WitchcraftBackend


def _has_search_deps() -> bool:
    try:
        import sqlite3

        import sentence_transformers  # noqa: F401
        import sqlite_vec

        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.close()
        return True
    except (ImportError, AttributeError, Exception):
        return False


# ── Helpers ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_session_uuid_deterministic(self):
        assert session_uuid("abc") == session_uuid("abc")

    def test_session_uuid_differs(self):
        assert session_uuid("abc") != session_uuid("xyz")

    def test_sanitize_strips_code_blocks(self):
        text = "before ```python\nprint('hi')\n``` after"
        assert "print" not in sanitize(text)
        assert "before" in sanitize(text)
        assert "after" in sanitize(text)

    def test_sanitize_strips_inline_code(self):
        assert "`foo`" not in sanitize("use `foo` here")

    def test_sanitize_strips_xml_tags(self):
        assert "secret" not in sanitize("<hidden>secret</hidden> visible")
        assert "visible" in sanitize("<hidden>secret</hidden> visible")

    def test_build_search_body(self):
        messages = [
            {"role": "human", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        body, lengths = build_search_body(messages)
        assert "[User]" in body
        assert "[Assistant]" in body
        assert len(lengths) == 2

    def test_build_search_body_skips_empty(self):
        messages = [{"role": "human", "content": ""}, {"role": "human", "content": "ok"}]
        body, lengths = build_search_body(messages)
        assert len(lengths) == 1

    def test_build_metadata(self):
        session = {
            "id": "s1",
            "project_path": "/p",
            "author": "alice",
            "source": "claude-code",
            "started_at": "2025-01-01",
            "summary": "test",
        }
        meta = build_metadata(session)
        assert meta["session_id"] == "s1"
        assert meta["author"] == "alice"


# ── ABC ─────────────────────────────────────────────────────────────


class TestSearchBackendABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            SearchBackend()  # type: ignore[abstract]


# ── Factory ─────────────────────────────────────────────────────────


class TestFactory:
    def test_witchcraft_backend(self):
        config = Config()
        config.search_backend = "witchcraft"
        backend = get_search_backend(config)
        assert isinstance(backend, WitchcraftBackend)

    def test_sqlite_vec_backend(self, tmp_path):
        config = Config()
        config.search_backend = "sqlite-vec"
        config.search_vec_db_path = tmp_path / "test_vec.db"
        backend = get_search_backend(config)
        from hive.search.sqlite_vec import SqliteVecBackend

        assert isinstance(backend, SqliteVecBackend)

    def test_unknown_backend_raises(self):
        config = Config()
        config.search_backend = "nonexistent"
        with pytest.raises(ValueError, match="Unknown search backend"):
            get_search_backend(config)

    def test_pgvector_requires_dsn(self):
        config = Config()
        config.search_backend = "pgvector"
        with pytest.raises(ValueError, match="pgvector backend requires"):
            get_search_backend(config)

    def test_pgvector_instantiates_with_dsn(self):
        from hive.search.pgvector import PgvectorBackend

        config = Config()
        config.search_backend = "pgvector"
        config.db_url = "postgresql://hive:hive@localhost:5432/hive"
        backend = get_search_backend(config)
        assert isinstance(backend, PgvectorBackend)

    def test_elasticsearch_not_implemented(self):
        config = Config()
        config.search_backend = "elasticsearch"
        backend = get_search_backend(config)
        with pytest.raises(NotImplementedError):
            backend.is_available()


# ── Witchcraft Backend ──────────────────────────────────────────────


class TestWitchcraftBackend:
    def test_unavailable_when_no_server(self):
        backend = WitchcraftBackend(base_url="http://localhost:0")
        assert backend.is_available() is False


# ── SQLite-vec Backend ──────────────────────────────────────────────


@pytest.mark.skipif(
    not _has_search_deps(),
    reason="sqlite-vec and/or sentence-transformers not installed",
)
class TestSqliteVecBackend:
    @pytest.fixture()
    def backend(self, tmp_path):
        from hive.search.sqlite_vec import SqliteVecBackend

        return SqliteVecBackend(db_path=tmp_path / "test_vec.db")

    def test_is_available(self, backend):
        assert backend.is_available() is True

    def test_add_and_search_round_trip(self, backend):
        backend.add_document(
            session_id="s1",
            date="2025-01-01",
            metadata={"session_id": "s1", "project_path": "/myproject", "author": "alice"},
            body="[User] How do I refactor the auth module?\n[Assistant] Use dependency injection.\n",
            chunk_lengths=[44, 35],
        )
        backend.trigger_index()

        results = backend.search("refactor auth")
        assert len(results) >= 1
        assert results[0]["metadata"]["session_id"] == "s1"
        assert results[0]["score"] > 0

    def test_remove_document(self, backend):
        backend.add_document(
            session_id="s2",
            date="2025-01-01",
            metadata={"session_id": "s2"},
            body="Some test content for removal",
            chunk_lengths=[29],
        )
        backend.trigger_index()

        backend.remove_document("s2")
        results = backend.search("test content removal")
        session_ids = [r["metadata"].get("session_id") for r in results]
        assert "s2" not in session_ids

    def test_trigger_index_returns_count(self, backend):
        backend.add_document(
            session_id="s3",
            date="2025-01-01",
            metadata={"session_id": "s3"},
            body="chunk one chunk two",
            chunk_lengths=[10, 9],
        )
        result = backend.trigger_index()
        assert result["embedded"] == 2

    def test_trigger_index_no_pending(self, backend):
        result = backend.trigger_index()
        assert result["embedded"] == 0

    def test_filter_by_project(self, backend):
        backend.add_document(
            session_id="s4",
            date="2025-01-01",
            metadata={"session_id": "s4", "project_path": "/project-a"},
            body="Alpha project work",
            chunk_lengths=[20],
        )
        backend.add_document(
            session_id="s5",
            date="2025-01-01",
            metadata={"session_id": "s5", "project_path": "/project-b"},
            body="Beta project work",
            chunk_lengths=[19],
        )
        backend.trigger_index()

        results = backend.search("project work", project="project-a")
        session_ids = [r["metadata"]["session_id"] for r in results]
        assert "s4" in session_ids
        assert "s5" not in session_ids

    def test_filter_by_author(self, backend):
        backend.add_document(
            session_id="s6",
            date="2025-01-01",
            metadata={"session_id": "s6", "author": "alice"},
            body="Alice wrote this code",
            chunk_lengths=[21],
        )
        backend.add_document(
            session_id="s7",
            date="2025-01-01",
            metadata={"session_id": "s7", "author": "bob"},
            body="Bob wrote this code",
            chunk_lengths=[19],
        )
        backend.trigger_index()

        results = backend.search("wrote code", author="alice")
        session_ids = [r["metadata"]["session_id"] for r in results]
        assert "s6" in session_ids
        assert "s7" not in session_ids
