"""Tests for hive enrichers (quality and files)."""

from __future__ import annotations

import json

import pytest

from hive.enrich.files import FilesEnricher
from hive.enrich.quality import QualityEnricher


def _make_session(messages: list[dict], **kwargs) -> dict:
    """Build a minimal session dict with the given messages."""
    return {
        "id": "test-sess",
        "source": "claude-code",
        "project_path": "/proj",
        "author": "dev",
        "started_at": kwargs.get("started_at", "2025-06-01T10:00:00"),
        "ended_at": kwargs.get("ended_at", "2025-06-01T10:30:00"),
        "message_count": len(messages),
        "summary": None,
        "messages": messages,
    }


class TestQualityEnricher:
    def test_message_count(self):
        enricher = QualityEnricher()
        session = _make_session(
            [
                {"role": "human", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "human", "content": "Thanks"},
            ]
        )
        result = enricher.run(session)
        assert result["message_count"] == 3

    def test_correction_frequency(self):
        enricher = QualityEnricher()
        session = _make_session(
            [
                {"role": "human", "content": "Do X"},
                {"role": "assistant", "content": "Done X."},
                {"role": "human", "content": "No, that's wrong, do Y instead"},
                {"role": "assistant", "content": "Done Y."},
                {"role": "human", "content": "Looks good"},
            ]
        )
        result = enricher.run(session)
        # 3 human messages; the second one has "No", "wrong", "instead" (correction).
        # The first and third have no correction signals.
        # So correction_frequency = 1/3
        assert result["correction_frequency"] == pytest.approx(1 / 3, abs=0.01)

    def test_correction_frequency_no_corrections(self):
        enricher = QualityEnricher()
        session = _make_session(
            [
                {"role": "human", "content": "Please help"},
                {"role": "assistant", "content": "Sure"},
            ]
        )
        result = enricher.run(session)
        assert result["correction_frequency"] == 0.0

    def test_correction_frequency_empty_messages(self):
        enricher = QualityEnricher()
        session = _make_session([])
        result = enricher.run(session)
        assert result["correction_frequency"] == 0.0
        assert result["message_count"] == 0

    def test_session_duration(self):
        enricher = QualityEnricher()
        session = _make_session(
            [{"role": "human", "content": "hi"}],
            started_at="2025-06-01T10:00:00",
            ended_at="2025-06-01T10:30:00",
        )
        result = enricher.run(session)
        assert result["session_duration"] == 1800.0  # 30 minutes in seconds

    def test_human_assistant_ratio(self):
        enricher = QualityEnricher()
        session = _make_session(
            [
                {"role": "human", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "human", "content": "q2"},
                {"role": "assistant", "content": "a2"},
            ]
        )
        result = enricher.run(session)
        assert result["human_assistant_ratio"] == 1.0

    def test_name(self):
        assert QualityEnricher().name() == "quality"

    def test_should_run(self):
        assert QualityEnricher().should_run({}) is True


class TestFilesEnricher:
    def test_extracts_paths_from_content(self):
        enricher = FilesEnricher()
        session = _make_session(
            [
                {
                    "role": "assistant",
                    "content": "I edited /home/dev/src/main.py and src/utils/helper.py",
                },
                {"role": "human", "content": "Also check /etc/config.yaml"},
            ]
        )
        result = enricher.run(session)
        assert "files_touched" in result
        files = result["files_touched"].split(",")
        assert "/home/dev/src/main.py" in files
        assert "/etc/config.yaml" in files

    def test_extracts_paths_from_tool_json(self):
        enricher = FilesEnricher()
        session = _make_session(
            [
                {
                    "role": "tool",
                    "tool_name": "Read",
                    "content": json.dumps({"file_path": "/proj/README.md"}),
                },
            ]
        )
        result = enricher.run(session)
        assert "files_touched" in result
        files = result["files_touched"].split(",")
        assert "/proj/README.md" in files

    def test_empty_messages_returns_empty(self):
        enricher = FilesEnricher()
        session = _make_session([])
        result = enricher.run(session)
        assert result == {}

    def test_no_paths_returns_empty(self):
        enricher = FilesEnricher()
        session = _make_session(
            [{"role": "human", "content": "Just a plain message with no file references"}]
        )
        result = enricher.run(session)
        assert result == {}

    def test_name(self):
        assert FilesEnricher().name() == "files"

    def test_should_run(self):
        assert FilesEnricher().should_run({}) is True
