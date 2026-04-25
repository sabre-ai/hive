"""Tests for deduplication and compaction gap fixes."""

from __future__ import annotations

from hive.store.query import QueryAPI

# ── Annotation dedup (Gap 5) ──────────────────────────────────────────


class TestAnnotationDedup:
    def test_duplicate_annotation_returns_existing_id(
        self, query_api: QueryAPI, sample_session: dict
    ):
        query_api.upsert_session(sample_session)
        id1 = query_api.write_annotation(sample_session["id"], "tag", "bugfix")
        id2 = query_api.write_annotation(sample_session["id"], "tag", "bugfix")
        assert id1 == id2

    def test_different_values_create_separate_annotations(
        self, query_api: QueryAPI, sample_session: dict
    ):
        query_api.upsert_session(sample_session)
        id1 = query_api.write_annotation(sample_session["id"], "tag", "bugfix")
        id2 = query_api.write_annotation(sample_session["id"], "tag", "feature")
        assert id1 != id2

    def test_delete_annotations(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.write_annotation(sample_session["id"], "tag", "a")
        query_api.write_annotation(sample_session["id"], "tag", "b")
        query_api.write_annotation(sample_session["id"], "comment", "note")

        query_api.delete_annotations(sample_session["id"], ann_type="tag")

        session = query_api.get_session(sample_session["id"])
        annotations = session["annotations"]
        assert len(annotations) == 1
        assert annotations[0]["type"] == "comment"


# ── Edge dedup (Gap 6) ────────────────────────────────────────────────


class TestEdgeDedup:
    def test_duplicate_edge_is_skipped(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.insert_edge("session", sample_session["id"], "file", "src/a.py", "touched")
        query_api.insert_edge("session", sample_session["id"], "file", "src/a.py", "touched")

        session = query_api.get_session(sample_session["id"])
        files = session.get("files_touched", [])
        assert files == ["src/a.py"]

    def test_different_targets_create_separate_edges(
        self, query_api: QueryAPI, sample_session: dict
    ):
        query_api.upsert_session(sample_session)
        query_api.insert_edge("session", sample_session["id"], "file", "src/a.py", "touched")
        query_api.insert_edge("session", sample_session["id"], "file", "src/b.py", "touched")

        session = query_api.get_session(sample_session["id"])
        files = session.get("files_touched", [])
        assert len(files) == 2


# ── Enrichment upsert (Gap 7) ────────────────────────────────────────


class TestEnrichmentUpsert:
    def test_upsert_updates_existing_value(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.insert_enrichment(sample_session["id"], "git", "branch", "main", upsert=True)
        query_api.insert_enrichment(sample_session["id"], "git", "branch", "develop", upsert=True)

        session = query_api.get_session(sample_session["id"])
        enrichments = session.get("enrichments", {})
        assert enrichments.get("git/branch") == "develop"

    def test_append_creates_multiple_rows(self, query_api: QueryAPI, sample_session: dict):
        query_api.upsert_session(sample_session)
        query_api.insert_enrichment(
            sample_session["id"], "compact_snapshot", "transcript_t1", "data1"
        )
        query_api.insert_enrichment(
            sample_session["id"], "compact_snapshot", "transcript_t2", "data2"
        )

        snapshots = query_api.get_compact_snapshots(sample_session["id"])
        assert len(snapshots) == 2
