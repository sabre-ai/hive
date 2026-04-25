"""Tests for deduplication and compaction gap fixes."""

from __future__ import annotations

import json
from pathlib import Path

from hive.capture.claude_code import ClaudeCodeAdapter
from hive.capture.claude_desktop import ClaudeDesktopAdapter
from hive.config import Config
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


# ── Compact snapshot keys (Gap 1) ────────────────────────────────────


class TestCompactSnapshotKeys:
    def test_two_pre_compacts_create_distinct_keys(
        self, tmp_path: Path, query_api: QueryAPI, config: Config
    ):
        session_id = "compact-test-001"
        query_api.upsert_session(
            {
                "id": session_id,
                "source": "claude-code",
                "project_path": str(tmp_path),
                "started_at": "2025-01-01T00:00:00",
                "message_count": 0,
            }
        )

        # Create a fake JSONL transcript
        jsonl_file = tmp_path / "transcript.jsonl"
        jsonl_file.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
                    "timestamp": "2025-01-01T00:00:00",
                }
            )
            + "\n"
        )

        adapter = ClaudeCodeAdapter(config=config)
        adapter._api = query_api

        data = {"session_id": session_id, "transcript_path": str(jsonl_file)}
        adapter._on_pre_compact(data)
        adapter._on_pre_compact(data)

        snapshots = query_api.get_compact_snapshots(session_id)
        assert len(snapshots) == 2


# ── Merge pre-compact content at Stop (Gaps 2 + 3) ───────────────────


class TestMergeCompactMessages:
    def _make_jsonl_line(self, role: str, text: str, ts: str) -> str:
        return json.dumps(
            {
                "type": role,
                "message": {
                    "role": role,
                    "content": [{"type": "text", "text": text}],
                },
                "timestamp": ts,
            }
        )

    def test_merge_restores_compacted_messages(
        self, tmp_path: Path, query_api: QueryAPI, config: Config
    ):
        session_id = "merge-test-001"
        query_api.upsert_session(
            {
                "id": session_id,
                "source": "claude-code",
                "project_path": str(tmp_path),
                "started_at": "2025-01-01T00:00:00",
                "message_count": 0,
            }
        )

        # Pre-compact snapshot has 3 messages
        snapshot_lines = "\n".join(
            [
                self._make_jsonl_line("user", "first question", "2025-01-01T00:01:00"),
                self._make_jsonl_line("assistant", "first answer", "2025-01-01T00:02:00"),
                self._make_jsonl_line("user", "second question", "2025-01-01T00:03:00"),
            ]
        )
        query_api.insert_enrichment(
            session_id, "compact_snapshot", "transcript_2025-01-01T00:04:00", snapshot_lines
        )

        # Post-compact JSONL has only the last message (simulating compaction)
        post_compact = tmp_path / "transcript.jsonl"
        post_compact.write_text(
            self._make_jsonl_line("user", "second question", "2025-01-01T00:03:00") + "\n"
        )

        adapter = ClaudeCodeAdapter(config=config)
        adapter._api = query_api

        # Parse JSONL (post-compact: 1 message)
        messages = adapter._parse_jsonl(session_id, post_compact)
        assert len(messages) == 1

        # Merge should restore the 2 compacted-away messages
        merged = adapter._merge_compact_messages(session_id, messages)
        assert len(merged) == 3

        # Ordinals should be sequential
        ordinals = [m["ordinal"] for m in merged]
        assert ordinals == [1, 2, 3]

    def test_merge_no_snapshots_returns_original(
        self, query_api: QueryAPI, config: Config, sample_session: dict
    ):
        query_api.upsert_session(sample_session)
        adapter = ClaudeCodeAdapter(config=config)
        adapter._api = query_api

        messages = [
            {"session_id": sample_session["id"], "ordinal": 1, "role": "user", "content": "hi"}
        ]
        result = adapter._merge_compact_messages(sample_session["id"], messages)
        assert result is messages

    def test_stop_indexes_merged_content_in_fts(
        self, tmp_path: Path, query_api: QueryAPI, config: Config
    ):
        session_id = "fts-merge-test"
        query_api.upsert_session(
            {
                "id": session_id,
                "source": "claude-code",
                "project_path": str(tmp_path),
                "started_at": "2025-01-01T00:00:00",
                "message_count": 0,
            }
        )

        # Pre-compact has a unique keyword
        snapshot_lines = self._make_jsonl_line(
            "user", "xylophone_unique_keyword", "2025-01-01T00:01:00"
        )
        query_api.insert_enrichment(
            session_id, "compact_snapshot", "transcript_2025-01-01T00:02:00", snapshot_lines
        )

        # Post-compact JSONL has different content
        post_compact = tmp_path / f"{session_id}.jsonl"
        post_compact.write_text(
            self._make_jsonl_line("user", "only remaining message", "2025-01-01T00:03:00") + "\n"
        )

        adapter = ClaudeCodeAdapter(config=config)
        adapter._api = query_api

        # Run the full _on_stop flow
        adapter._on_stop(
            {
                "session_id": session_id,
                "project_path": str(tmp_path),
                "transcript_path": str(post_compact),
            }
        )

        # The unique keyword from the snapshot should be searchable via FTS
        results = query_api.search_sessions("xylophone_unique_keyword")
        assert len(results) > 0
        assert results[0]["id"] == session_id


# ── capture_session re-capture (Gap 4) ────────────────────────────────


class TestCaptureSessionRecapture:
    def test_recapture_with_session_id_replaces_content(self, query_api: QueryAPI, config: Config):
        adapter = ClaudeDesktopAdapter(config=config, skip_init=True)
        adapter._api = query_api

        session_id = "recapture-test-001"

        # First capture
        adapter._ingest(
            {
                "title": "Test session",
                "content": "Human: hello\nAssistant: hi",
                "tags": ["draft"],
                "session_id": session_id,
            }
        )

        # Re-capture with more content
        adapter._ingest(
            {
                "title": "Test session updated",
                "content": "Human: hello\nAssistant: hi\nHuman: how are you\nAssistant: great",
                "tags": ["final"],
                "session_id": session_id,
            }
        )

        session = query_api.get_session(session_id)
        assert session is not None
        assert session["summary"] == "Test session updated"
        assert session["message_count"] == 4

        # Tags should not be duplicated
        annotations = session["annotations"]
        tag_values = [a["value"] for a in annotations if a["type"] == "tag"]
        assert "final" in tag_values
        # "draft" was deleted on re-capture
        assert "draft" not in tag_values

    def test_capture_without_session_id_uses_content_hash(
        self, query_api: QueryAPI, config: Config
    ):
        adapter = ClaudeDesktopAdapter(config=config, skip_init=True)
        adapter._api = query_api

        sid1 = adapter._ingest(
            {"title": "Test", "content": "Human: hello\nAssistant: hi", "tags": []}
        )
        sid2 = adapter._ingest(
            {"title": "Test", "content": "Human: hello\nAssistant: hi", "tags": []}
        )
        # Same content = same session ID (idempotent)
        assert sid1 == sid2

    def test_capture_different_content_creates_new_session(
        self, query_api: QueryAPI, config: Config
    ):
        adapter = ClaudeDesktopAdapter(config=config, skip_init=True)
        adapter._api = query_api

        sid1 = adapter._ingest(
            {"title": "Test", "content": "Human: hello\nAssistant: hi", "tags": []}
        )
        sid2 = adapter._ingest(
            {"title": "Test", "content": "Human: goodbye\nAssistant: bye", "tags": []}
        )
        assert sid1 != sid2
