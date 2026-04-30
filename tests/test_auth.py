"""Tests for the auth module."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from hive.auth.config import AuthConfig
from hive.auth.models import RefreshToken, User
from hive.auth.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    validate_access_token,
)
from hive.config import Config
from hive.serve.api import create_app
from hive.store.db import get_session_factory, init_db


@pytest.fixture
def auth_config():
    return AuthConfig(
        enabled=True,
        issuer_url="https://accounts.example.com",
        client_id="test-client",
        client_secret="test-secret",
        jwt_secret="test-jwt-secret-256-bits-long-enough",
        access_token_ttl_minutes=60,
        refresh_token_ttl_days=30,
    )


@pytest.fixture
def test_db(tmp_path):
    config = Config()
    config.db_path = tmp_path / "test.db"
    db_path = config.db_path
    init_db(config, db_path=db_path)
    return config, db_path


# ── Token tests ──────────────────────────────────────────────────────


class TestTokens:
    def test_create_and_validate_access_token(self, auth_config):
        token = create_access_token("user-123", "alice@example.com", "Alice", auth_config)
        claims = validate_access_token(token, auth_config.jwt_secret)

        assert claims["sub"] == "user-123"
        assert claims["email"] == "alice@example.com"
        assert claims["name"] == "Alice"
        assert claims["iss"] == "hive"
        assert claims["aud"] == "hive"

    def test_expired_token_raises(self, auth_config):
        auth_config.access_token_ttl_minutes = -1  # Already expired
        token = create_access_token("user-123", "alice@example.com", "Alice", auth_config)

        with pytest.raises(jwt.ExpiredSignatureError):
            validate_access_token(token, auth_config.jwt_secret)

    def test_invalid_secret_raises(self, auth_config):
        token = create_access_token("user-123", "alice@example.com", "Alice", auth_config)

        with pytest.raises(jwt.InvalidSignatureError):
            validate_access_token(token, "wrong-secret")

    def test_refresh_token_is_unique(self):
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2
        assert t1.startswith("rt_")

    def test_hash_refresh_token_deterministic(self):
        token = "rt_test-token"
        h1 = hash_refresh_token(token)
        h2 = hash_refresh_token(token)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_refresh_token_expiry(self, auth_config):
        exp = refresh_token_expiry(auth_config)
        exp_dt = datetime.fromisoformat(exp)
        now = datetime.now(timezone.utc)
        # Should be ~30 days in the future
        delta = exp_dt - now
        assert 29 <= delta.days <= 31


# ── Config tests ─────────────────────────────────────────────────────


class TestAuthConfig:
    def test_load_defaults(self):
        cfg = AuthConfig.load(None)
        assert cfg.enabled is False
        assert cfg.jwt_secret == ""

    def test_load_from_toml_section(self):
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://accounts.google.com",
                "client_id": "my-id",
                "client_secret": "my-secret",
                "jwt_secret": "my-jwt-secret",
            }
        }
        cfg = AuthConfig.load(raw)
        assert cfg.enabled is True
        assert cfg.issuer_url == "https://accounts.google.com"
        assert cfg.client_id == "my-id"

    def test_env_overrides(self):
        with patch.dict(
            "os.environ",
            {
                "HIVE_AUTH_ENABLED": "true",
                "HIVE_AUTH_ISSUER_URL": "https://env.example.com",
                "HIVE_AUTH_JWT_SECRET": "env-secret",
            },
        ):
            cfg = AuthConfig.load(None)
            assert cfg.enabled is True
            assert cfg.issuer_url == "https://env.example.com"
            assert cfg.jwt_secret == "env-secret"

    def test_auto_generate_jwt_secret(self):
        raw = {"auth": {"enabled": True, "issuer_url": "https://example.com"}}
        cfg = AuthConfig.load(raw)
        assert cfg.jwt_secret != ""


# ── Middleware tests ──────────────────────────────────────────────────


class TestMiddleware:
    def test_auth_disabled_passes_through(self, test_db):
        config, db_path = test_db
        raw = {"auth": {"enabled": False}}
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # Should work without any auth header
        r = client.get("/api/sessions")
        assert r.status_code == 200

    def test_auth_enabled_rejects_unauthenticated_write(self, test_db):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://example.com",
                "client_id": "test",
                "jwt_secret": "test-secret-long-enough-for-hs256",
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # POST /api/sessions without auth should 401
        r = client.post("/api/sessions", json={"id": "test", "source": "test"})
        assert r.status_code == 401

    def test_auth_enabled_accepts_valid_token(self, test_db):
        config, db_path = test_db
        jwt_secret = "test-secret-long-enough-for-hs256"
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://example.com",
                "client_id": "test",
                "jwt_secret": jwt_secret,
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # Create a valid token
        auth_cfg = AuthConfig(enabled=True, jwt_secret=jwt_secret, access_token_ttl_minutes=60)
        token = create_access_token("user-1", "alice@example.com", "Alice", auth_cfg)

        # POST /api/sessions with valid auth should succeed
        r = client.post(
            "/api/sessions",
            json={"id": str(uuid.uuid4()), "source": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201

    def test_auth_enforces_author_from_jwt(self, test_db):
        config, db_path = test_db
        jwt_secret = "test-secret-long-enough-for-hs256"
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://example.com",
                "client_id": "test",
                "jwt_secret": jwt_secret,
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        auth_cfg = AuthConfig(enabled=True, jwt_secret=jwt_secret, access_token_ttl_minutes=60)
        token = create_access_token("user-1", "alice@example.com", "Alice", auth_cfg)

        session_id = str(uuid.uuid4())
        # Client sends author="attacker" but server should override with JWT email
        r = client.post(
            "/api/sessions",
            json={"id": session_id, "source": "test", "author": "attacker"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201

        # Verify the session was stored with the JWT author
        r2 = client.get(f"/api/sessions/{session_id}")
        assert r2.status_code == 200
        assert r2.json()["author"] == "alice@example.com"

    def test_reads_work_without_auth_when_enabled(self, test_db):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://example.com",
                "client_id": "test",
                "jwt_secret": "test-secret-long-enough-for-hs256",
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # GET /api/sessions (read) should still work without auth
        r = client.get("/api/sessions")
        assert r.status_code == 200

    def test_health_always_public(self, test_db):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://example.com",
                "client_id": "test",
                "jwt_secret": "test-secret-long-enough-for-hs256",
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Auth discovery endpoint ───────────────────────────────────────────


class TestAuthEndpoints:
    def test_discovery_when_disabled(self, test_db):
        config, db_path = test_db
        raw = {"auth": {"enabled": False}}
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # Auth routes are not mounted when disabled, so check 404
        r = client.get("/auth/discovery")
        assert r.status_code == 404

    def test_discovery_when_enabled(self, test_db):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": "https://accounts.google.com",
                "client_id": "test-client",
                "jwt_secret": "test-secret-long-enough-for-hs256",
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # Mock the OIDC discovery fetch
        with patch("hive.auth.oidc.fetch_discovery") as mock_disc:
            from hive.auth.oidc import OIDCDiscovery

            mock_disc.return_value = OIDCDiscovery(
                issuer="https://accounts.google.com",
                authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
                token_endpoint="https://accounts.google.com/token",
                jwks_uri="https://accounts.google.com/jwks",
            )
            r = client.get("/auth/discovery")
            assert r.status_code == 200
            data = r.json()
            assert data["auth_enabled"] is True
            assert data["client_id"] == "test-client"


# ── Refresh token rotation ────────────────────────────────────────────


class TestRefreshTokenRotation:
    def test_refresh_issues_new_tokens(self, test_db, auth_config):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": auth_config.issuer_url,
                "client_id": auth_config.client_id,
                "jwt_secret": auth_config.jwt_secret,
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        # Seed a user and refresh token
        session_factory = get_session_factory(config, db_path=db_path)
        user_id = str(uuid.uuid4())
        refresh = create_refresh_token()

        with session_factory() as db:
            db.add(User(id=user_id, email="bob@example.com", name="Bob"))
            db.add(
                RefreshToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=hash_refresh_token(refresh),
                    expires_at=refresh_token_expiry(auth_config),
                )
            )
            db.commit()

        # Refresh
        r = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh  # Rotated

    def test_reuse_detection_revokes_all(self, test_db, auth_config):
        config, db_path = test_db
        raw = {
            "auth": {
                "enabled": True,
                "issuer_url": auth_config.issuer_url,
                "client_id": auth_config.client_id,
                "jwt_secret": auth_config.jwt_secret,
            }
        }
        app = create_app(config=config, db_path=db_path, raw_config=raw)
        client = TestClient(app)

        session_factory = get_session_factory(config, db_path=db_path)
        user_id = str(uuid.uuid4())
        refresh = create_refresh_token()

        with session_factory() as db:
            db.add(User(id=user_id, email="carol@example.com", name="Carol"))
            db.add(
                RefreshToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=hash_refresh_token(refresh),
                    expires_at=refresh_token_expiry(auth_config),
                )
            )
            db.commit()

        # First refresh succeeds
        r1 = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r1.status_code == 200

        # Reuse the OLD token — should be detected and rejected
        r2 = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code == 401

        # The new token from r1 should ALSO be revoked (reuse detection)
        new_refresh = r1.json()["refresh_token"]
        r3 = client.post("/auth/refresh", json={"refresh_token": new_refresh})
        assert r3.status_code == 401
