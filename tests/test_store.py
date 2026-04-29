"""Tests for hive.store.query.QueryAPI."""

from __future__ import annotations

from hive.store.query import QueryAPI


class TestUpsertAndGetSession:
    def test_upsert_and_get_session(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        result = query_api.get_session(sample_session["id"])

        assert result is not None
        assert result["id"] == sample_session["id"]
        assert result["source"] == "claude-code"
        assert result["author"] == "alice"
        assert result["summary"] == "Refactored the auth module"
        assert result["message_count"] == 4

    def test_upsert_updates_existing_session(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)

        updated = {**sample_session, "message_count": 8, "summary": "New summary"}
        query_api.upsert_session(updated)

        result = query_api.get_session(sample_session["id"])
        assert result["message_count"] == 8
        assert result["summary"] == "New summary"

    def test_get_session_returns_none_for_missing(self, query_api: QueryAPI):
        assert query_api.get_session("nonexistent") is None


class TestListSessions:
    def _seed(self, query_api: QueryAPI):
        sessions = [
            {
                "id": "s1",
                "source": "claude-code",
                "project_path": "/proj/alpha",
                "author": "alice",
                "started_at": "2025-06-01T10:00:00",
                "ended_at": "2025-06-01T10:30:00",
                "message_count": 3,
                "summary": "First session",
            },
            {
                "id": "s2",
                "source": "claude-code",
                "project_path": "/proj/beta",
                "author": "bob",
                "started_at": "2025-06-02T10:00:00",
                "ended_at": "2025-06-02T10:30:00",
                "message_count": 5,
                "summary": "Second session",
            },
            {
                "id": "s3",
                "source": "git-hook",
                "project_path": "/proj/alpha",
                "author": "alice",
                "started_at": "2025-06-03T10:00:00",
                "ended_at": "2025-06-03T10:30:00",
                "message_count": 2,
                "summary": "Third session",
            },
        ]
        for s in sessions:
            query_api.upsert_session(s)

    def test_list_all(self, query_api: QueryAPI):
        self._seed(query_api)
        results = query_api.list_sessions()
        assert len(results) == 3

    def test_filter_by_project(self, query_api: QueryAPI):
        self._seed(query_api)
        results = query_api.list_sessions(project="alpha")
        assert len(results) == 2
        assert all("alpha" in r["project_path"] for r in results)

    def test_filter_by_author(self, query_api: QueryAPI):
        self._seed(query_api)
        results = query_api.list_sessions(author="bob")
        assert len(results) == 1
        assert results[0]["id"] == "s2"

    def test_filter_by_since(self, query_api: QueryAPI):
        self._seed(query_api)
        results = query_api.list_sessions(since="2025-06-02T00:00:00")
        assert len(results) == 2
        ids = {r["id"] for r in results}
        assert ids == {"s2", "s3"}


class TestFTS:
    def test_insert_and_search_fts(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.index_session_fts(
            sample_session["id"],
            "refactored auth module dependency injection",
        )
        results = query_api.search_sessions("refactor")
        assert len(results) >= 1
        assert results[0]["id"] == sample_session["id"]

    def test_search_no_results(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.index_session_fts(sample_session["id"], "some content")
        results = query_api.search_sessions("zzzznonexistent")
        assert results == []


class TestDeleteSession:
    def test_delete_session_cascades(self, query_api: QueryAPI, sample_payload: dict):
        query_api.import_session(sample_payload)
        session_id = sample_payload["id"]

        # Verify data exists first
        session = query_api.get_session(session_id, detail="messages")
        assert session is not None
        assert len(session["messages"]) == 4
        assert len(session["enrichments"]) == 2

        # Delete
        deleted = query_api.delete_session(session_id)
        assert deleted is True

        # Verify all data is gone
        assert query_api.get_session(session_id, detail="messages") is None

        # Verify FTS is also cleaned
        results = query_api.search_sessions("refactor")
        assert results == []

    def test_delete_nonexistent_returns_false(self, query_api: QueryAPI):
        assert query_api.delete_session("nonexistent") is False


class TestExportSession:
    def test_export_session_includes_edges(self, query_api: QueryAPI, sample_payload: dict):
        query_api.import_session(sample_payload)
        exported = query_api.export_session(sample_payload["id"])

        assert exported is not None
        assert "edges" in exported
        assert len(exported["edges"]) == 2
        edge_relationships = {e["relationship"] for e in exported["edges"]}
        assert "modified" in edge_relationships
        assert "produced" in edge_relationships

    def test_export_nonexistent_returns_none(self, query_api: QueryAPI):
        assert query_api.export_session("nonexistent") is None


class TestImportSession:
    def test_import_session_roundtrip(self, query_api: QueryAPI, sample_payload: dict):
        query_api.import_session(sample_payload)
        session = query_api.get_session(sample_payload["id"], detail="messages")

        assert session is not None
        assert session["id"] == sample_payload["id"]
        assert session["source"] == "claude-code"
        assert len(session["messages"]) == 4
        assert len(session["enrichments"]) == 2
        assert session["messages"][0]["role"] == "human"
        assert session["messages"][1]["role"] == "assistant"

    def test_import_idempotent(self, query_api: QueryAPI, sample_payload: dict):
        """Re-importing the same payload should not duplicate data."""
        query_api.import_session(sample_payload)
        query_api.import_session(sample_payload)

        session = query_api.get_session(sample_payload["id"], detail="messages")
        assert session is not None
        assert len(session["messages"]) == 4
        assert len(session["enrichments"]) == 2


class TestListProjects:
    def test_list_projects(self, query_api: QueryAPI):
        for i, proj in enumerate(["/proj/a", "/proj/a", "/proj/b"]):
            query_api.upsert_session(
                {
                    "id": f"lp-{i}",
                    "source": "claude-code",
                    "project_path": proj,
                    "author": "dev",
                    "started_at": f"2025-06-0{i + 1}T10:00:00",
                    "ended_at": f"2025-06-0{i + 1}T10:30:00",
                    "message_count": i + 1,
                    "summary": None,
                }
            )
        projects = query_api.list_projects()
        assert len(projects) == 2
        names = {p["project"] for p in projects}
        assert names == {"/proj/a", "/proj/b"}

        proj_a = next(p for p in projects if p["project"] == "/proj/a")
        assert proj_a["session_count"] == 2

    def test_list_projects_groups_by_project_id(self, query_api: QueryAPI):
        """Sessions with same project_id but different paths should merge."""
        for i, (path, pid) in enumerate(
            [
                ("/Users/alice/app", "github.com/acme/app"),
                ("/home/bob/app", "github.com/acme/app"),
                ("/proj/other", None),
            ]
        ):
            query_api.upsert_session(
                {
                    "id": f"pid-{i}",
                    "source": "claude-code",
                    "project_path": path,
                    "project_id": pid,
                    "author": "dev",
                    "started_at": f"2025-06-0{i + 1}T10:00:00",
                    "ended_at": f"2025-06-0{i + 1}T10:30:00",
                    "message_count": 1,
                    "summary": None,
                }
            )
        projects = query_api.list_projects()
        names = {p["project"] for p in projects}
        assert names == {"github.com/acme/app", "/proj/other"}

        acme = next(p for p in projects if p["project"] == "github.com/acme/app")
        assert acme["session_count"] == 2


class TestProjectId:
    def test_upsert_stores_project_id(self, query_api: QueryAPI):
        query_api.upsert_session(
            {
                "id": "pid-test-1",
                "source": "claude-code",
                "project_path": "/Users/alice/app",
                "project_id": "github.com/acme/app",
                "author": "alice",
                "started_at": "2025-06-01T10:00:00",
                "message_count": 0,
                "summary": None,
            }
        )
        result = query_api.get_session("pid-test-1")
        assert result["project_id"] == "github.com/acme/app"

    def test_list_sessions_matches_project_id(self, query_api: QueryAPI):
        query_api.upsert_session(
            {
                "id": "pid-filter-1",
                "source": "claude-code",
                "project_path": "/Users/alice/repos/app",
                "project_id": "github.com/acme/app",
                "author": "alice",
                "started_at": "2025-06-01T10:00:00",
                "message_count": 1,
                "summary": None,
            }
        )
        # Should match by project_id
        results = query_api.list_sessions(project="github.com/acme/app")
        assert len(results) == 1
        assert results[0]["id"] == "pid-filter-1"

    def test_import_session_auto_registers_project(self, query_api: QueryAPI):
        payload = {
            "id": "import-proj-1",
            "source": "claude-code",
            "project_path": "/Users/alice/app",
            "project_id": "github.com/acme/app",
            "author": "alice",
            "started_at": "2025-06-01T10:00:00",
            "ended_at": "2025-06-01T10:30:00",
            "message_count": 0,
            "summary": None,
            "messages": [],
            "enrichments": [],
            "annotations": [],
            "edges": [],
        }
        query_api.import_session(payload)
        result = query_api.get_session("import-proj-1")
        assert result["project_id"] == "github.com/acme/app"

    def test_ensure_project_is_idempotent(self, query_api: QueryAPI):
        query_api.ensure_project("github.com/acme/app", author="alice")
        query_api.ensure_project("github.com/acme/app", author="bob")
        # No error raised — second call is a no-op
