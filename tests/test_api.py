"""Tests for hive.serve.api REST endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hive.config import Config
from hive.serve.api import create_app
from hive.store.db import init_db
from hive.store.query import QueryAPI


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Create a TestClient backed by a temporary database."""
    db_path = tmp_path / "api_test.db"
    conn = init_db(db_path=db_path)
    conn.close()
    cfg = Config()
    cfg.db_path = db_path
    app = create_app(config=cfg, db_path=db_path)
    return TestClient(app)


@pytest.fixture()
def seeded_client(tmp_path: Path, sample_payload: dict) -> TestClient:
    """Create a TestClient with one session already imported."""
    db_path = tmp_path / "api_seeded.db"
    conn = init_db(db_path=db_path)
    conn.close()
    cfg = Config()
    cfg.db_path = db_path
    api = QueryAPI(config=cfg, db_path=db_path)
    api.import_session(sample_payload)
    app = create_app(config=cfg, db_path=db_path)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestPushSession:
    def test_push_session(self, client: TestClient, sample_payload: dict):
        resp = client.post("/api/sessions", json=sample_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ok"
        assert data["session_id"] == sample_payload["id"]

        # Verify it was persisted
        resp2 = client.get(f"/api/sessions/{sample_payload['id']}?detail=messages")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == sample_payload["id"]


class TestListSessions:
    def test_list_sessions(self, seeded_client: TestClient):
        resp = seeded_client.get("/api/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 1

    def test_list_sessions_empty(self, client: TestClient):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetSession:
    def test_get_session_404(self, client: TestClient):
        resp = client.get("/api/sessions/nonexistent-id")
        assert resp.status_code == 404

    def test_get_session_found(self, seeded_client: TestClient, sample_payload: dict):
        resp = seeded_client.get(f"/api/sessions/{sample_payload['id']}?detail=messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_payload["id"]
        assert len(data["messages"]) == 4


class TestDeleteSession:
    def test_delete_session(self, seeded_client: TestClient, sample_payload: dict):
        resp = seeded_client.delete(f"/api/sessions/{sample_payload['id']}?detail=messages")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify gone
        resp2 = seeded_client.get(f"/api/sessions/{sample_payload['id']}?detail=messages")
        assert resp2.status_code == 404

    def test_delete_session_404(self, client: TestClient):
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404


class TestSearch:
    def test_search(self, seeded_client: TestClient):
        resp = seeded_client.get("/api/search", params={"q": "refactor"})
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_search_no_results(self, seeded_client: TestClient):
        resp = seeded_client.get("/api/search", params={"q": "zzzznonexistent"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_requires_query(self, client: TestClient):
        resp = client.get("/api/search")
        assert resp.status_code == 422


class TestAnnotations:
    def test_annotations(self, seeded_client: TestClient, sample_payload: dict):
        body = {
            "session_id": sample_payload["id"],
            "type": "tag",
            "value": "important",
            "author": "tester",
        }
        resp = seeded_client.post("/api/annotations", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "tag"
        assert data["value"] == "important"
        assert data["author"] == "tester"
        assert data["session_id"] == sample_payload["id"]
        assert "id" in data
