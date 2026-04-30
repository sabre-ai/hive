"""JWT creation/validation and refresh token management."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from hive.auth.config import AuthConfig

logger = logging.getLogger(__name__)


def create_access_token(
    user_id: str,
    email: str,
    name: str | None,
    config: AuthConfig,
) -> str:
    """Create a signed Hive JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name or "",
        "iss": "hive",
        "aud": "hive",
        "iat": now,
        "exp": now + timedelta(minutes=config.access_token_ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def validate_access_token(token: str, jwt_secret: str) -> dict:
    """Validate and decode a Hive JWT access token.

    Returns the decoded claims dict.
    Raises jwt.InvalidTokenError on any validation failure.
    """
    return jwt.decode(
        token,
        jwt_secret,
        algorithms=["HS256"],
        audience="hive",
        issuer="hive",
    )


def create_refresh_token() -> str:
    """Generate a cryptographically random refresh token."""
    return f"rt_{secrets.token_urlsafe(48)}"


def hash_refresh_token(token: str) -> str:
    """SHA-256 hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expiry(config: AuthConfig) -> str:
    """Return ISO-8601 expiry timestamp for a new refresh token."""
    exp = datetime.now(timezone.utc) + timedelta(days=config.refresh_token_ttl_days)
    return exp.isoformat()
