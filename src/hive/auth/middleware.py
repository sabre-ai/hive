"""FastAPI dependencies for authentication."""

from __future__ import annotations

import logging

import jwt
from fastapi import Depends, HTTPException, Request

from hive.auth.config import AuthConfig

logger = logging.getLogger(__name__)

# Module-level auth config — set by create_app() during startup
_auth_config: AuthConfig | None = None


def set_auth_config(config: AuthConfig) -> None:
    """Called once at app startup to inject the auth config."""
    global _auth_config
    _auth_config = config


def _get_auth_config() -> AuthConfig:
    if _auth_config is None:
        return AuthConfig()
    return _auth_config


def _extract_bearer_token(request: Request) -> str | None:
    """Extract the Bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(request: Request) -> dict | None:
    """FastAPI dependency: extract and validate the user from the JWT.

    Returns a dict with user claims (sub, email, name) or None if auth is disabled.
    Raises 401 if auth is enabled and the token is missing or invalid.
    """
    config = _get_auth_config()
    if not config.enabled:
        return None

    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token. Run 'hive login' to authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from hive.auth.tokens import validate_access_token

        claims = validate_access_token(token, config.jwt_secret)
        return claims
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Run 'hive login' to re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_auth(user: dict | None = Depends(get_current_user)) -> dict | None:  # noqa: B008
    """FastAPI dependency for write endpoints.

    When auth is enabled, requires a valid user. When auth is disabled, returns None.
    """
    config = _get_auth_config()
    if config.enabled and user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
