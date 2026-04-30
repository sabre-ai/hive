"""FastAPI auth routes: /auth/* endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hive.auth.config import AuthConfig
from hive.auth.middleware import require_auth
from hive.auth.models import RefreshToken, User
from hive.auth.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)

logger = logging.getLogger(__name__)


# ── Request / response models ───────────────────────────────────────


class AuthCallbackRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserInfoResponse(BaseModel):
    id: str
    email: str
    name: str | None
    created_at: str | None


# ── Router factory ──────────────────────────────────────────────────


def create_auth_router(auth_config: AuthConfig, session_factory) -> APIRouter:
    """Build the /auth router with the given config and DB session factory."""
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/discovery")
    async def discovery():
        """Return OIDC config the CLI needs for login."""
        if not auth_config.enabled:
            return {"auth_enabled": False}

        from hive.auth.oidc import fetch_discovery

        disc = await fetch_discovery(auth_config.issuer_url)
        return {
            "auth_enabled": True,
            "issuer_url": auth_config.issuer_url,
            "client_id": auth_config.client_id,
            "scopes": auth_config.scopes,
            "authorization_endpoint": disc.authorization_endpoint,
        }

    @router.post("/callback", response_model=TokenResponse)
    async def callback(body: AuthCallbackRequest):
        """Exchange authorization code for Hive tokens."""
        if not auth_config.enabled:
            raise HTTPException(400, "Authentication is not enabled on this server.")

        from hive.auth.oidc import exchange_code, extract_user_info, validate_id_token

        # Exchange code with IdP
        try:
            token_response = await exchange_code(
                auth_config,
                code=body.code,
                code_verifier=body.code_verifier,
                redirect_uri=body.redirect_uri,
            )
        except Exception as e:
            logger.error("OIDC token exchange failed: %s", e)
            raise HTTPException(400, f"Token exchange failed: {e}") from e

        # Validate ID token
        id_token = token_response.get("id_token", "")
        if not id_token:
            raise HTTPException(400, "No id_token in provider response.")

        try:
            claims = validate_id_token(id_token, auth_config)
        except Exception as e:
            logger.error("ID token validation failed: %s", e)
            raise HTTPException(400, f"ID token validation failed: {e}") from e

        user_info = extract_user_info(claims)
        email = user_info["email"]
        if not email:
            raise HTTPException(400, "Email not provided by identity provider.")

        # Check domain allowlist
        if auth_config.allowed_domains:
            domain = email.split("@")[-1]
            if domain not in auth_config.allowed_domains:
                raise HTTPException(403, f"Email domain '{domain}' is not allowed.")

        # Upsert user
        now = datetime.now(timezone.utc).isoformat()
        with session_factory() as db:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    name=user_info.get("name"),
                    oidc_subject=user_info.get("sub"),
                    oidc_issuer=auth_config.issuer_url,
                    created_at=now,
                    last_login_at=now,
                )
                db.add(user)
            else:
                user.last_login_at = now
                if user_info.get("name"):
                    user.name = user_info["name"]

            # Issue Hive tokens
            access = create_access_token(user.id, user.email, user.name, auth_config)
            refresh = create_refresh_token()

            # Store refresh token hash
            rt = RefreshToken(
                id=str(uuid.uuid4()),
                user_id=user.id,
                token_hash=hash_refresh_token(refresh),
                expires_at=refresh_token_expiry(auth_config),
            )
            db.add(rt)
            db.commit()

            return TokenResponse(
                access_token=access,
                refresh_token=refresh,
                expires_in=auth_config.access_token_ttl_minutes * 60,
                user={"email": user.email, "name": user.name},
            )

    @router.post("/refresh", response_model=TokenResponse)
    async def refresh(body: RefreshRequest):
        """Rotate refresh token and issue new access token."""
        if not auth_config.enabled:
            raise HTTPException(400, "Authentication is not enabled.")

        token_hash = hash_refresh_token(body.refresh_token)
        now = datetime.now(timezone.utc)

        with session_factory() as db:
            rt = (
                db.query(RefreshToken)
                .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
                .first()
            )

            if rt is None:
                # Possible replay attack — check if this token was already used
                revoked = (
                    db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
                )
                if revoked:
                    # Reuse detection: revoke ALL tokens for this user
                    db.query(RefreshToken).filter(
                        RefreshToken.user_id == revoked.user_id,
                        RefreshToken.revoked_at.is_(None),
                    ).update({"revoked_at": now.isoformat()})
                    db.commit()
                    logger.warning(
                        "Refresh token reuse detected for user %s — all tokens revoked",
                        revoked.user_id,
                    )
                raise HTTPException(401, "Invalid or revoked refresh token.")

            # Check expiry
            if rt.expires_at < now.isoformat():
                rt.revoked_at = now.isoformat()
                db.commit()
                raise HTTPException(401, "Refresh token expired. Run 'hive login'.")

            # Revoke old, issue new
            rt.revoked_at = now.isoformat()

            user = db.query(User).filter(User.id == rt.user_id).first()
            if user is None:
                raise HTTPException(401, "User not found.")

            access = create_access_token(user.id, user.email, user.name, auth_config)
            new_refresh = create_refresh_token()

            new_rt = RefreshToken(
                id=str(uuid.uuid4()),
                user_id=user.id,
                token_hash=hash_refresh_token(new_refresh),
                expires_at=refresh_token_expiry(auth_config),
            )
            db.add(new_rt)
            db.commit()

            return TokenResponse(
                access_token=access,
                refresh_token=new_refresh,
                expires_in=auth_config.access_token_ttl_minutes * 60,
                user={"email": user.email, "name": user.name},
            )

    @router.post("/logout")
    async def logout(body: LogoutRequest, user: dict | None = Depends(require_auth)):  # noqa: B008
        """Revoke a refresh token."""
        token_hash = hash_refresh_token(body.refresh_token)
        now = datetime.now(timezone.utc).isoformat()

        with session_factory() as db:
            rt = (
                db.query(RefreshToken)
                .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
                .first()
            )
            if rt:
                rt.revoked_at = now
                db.commit()

        return {"status": "ok"}

    @router.get("/userinfo", response_model=UserInfoResponse)
    async def userinfo(user: dict | None = Depends(require_auth)):  # noqa: B008
        """Return info about the currently authenticated user."""
        if user is None:
            raise HTTPException(401, "Not authenticated.")

        with session_factory() as db:
            db_user = db.query(User).filter(User.id == user["sub"]).first()
            if db_user is None:
                raise HTTPException(404, "User not found.")
            return UserInfoResponse(
                id=db_user.id,
                email=db_user.email,
                name=db_user.name,
                created_at=db_user.created_at,
            )

    return router
