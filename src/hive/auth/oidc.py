"""OIDC provider interaction — discovery, token exchange, ID token validation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
import jwt
from jwt import PyJWKClient

from hive.auth.config import AuthConfig

logger = logging.getLogger(__name__)


@dataclass
class OIDCDiscovery:
    """Cached OIDC provider metadata."""

    issuer: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    _fetched_at: float = 0.0
    _ttl: float = 3600.0  # 1 hour cache

    def is_stale(self) -> bool:
        return time.time() - self._fetched_at > self._ttl


# Module-level cache
_discovery_cache: dict[str, OIDCDiscovery] = {}
_jwk_clients: dict[str, PyJWKClient] = {}


async def fetch_discovery(issuer_url: str) -> OIDCDiscovery:
    """Fetch and cache the OIDC provider's .well-known/openid-configuration."""
    cached = _discovery_cache.get(issuer_url)
    if cached and not cached.is_stale():
        return cached

    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    discovery = OIDCDiscovery(
        issuer=data["issuer"],
        authorization_endpoint=data["authorization_endpoint"],
        token_endpoint=data["token_endpoint"],
        userinfo_endpoint=data.get("userinfo_endpoint", ""),
        jwks_uri=data["jwks_uri"],
        _fetched_at=time.time(),
    )
    _discovery_cache[issuer_url] = discovery
    return discovery


async def exchange_code(
    config: AuthConfig,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    """Exchange an authorization code for tokens at the IdP's token endpoint.

    Returns the raw token response dict (id_token, access_token, etc.).
    """
    discovery = await fetch_discovery(config.issuer_url)

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            discovery.token_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        return r.json()


def validate_id_token(id_token: str, config: AuthConfig) -> dict:
    """Validate an OIDC ID token using the provider's JWKS keys.

    Returns the decoded claims dict.
    Raises jwt.InvalidTokenError on any validation failure.
    """
    jwks_uri = _discovery_cache.get(config.issuer_url, OIDCDiscovery()).jwks_uri
    if not jwks_uri:
        raise ValueError("OIDC discovery not fetched yet — call fetch_discovery first")

    if jwks_uri not in _jwk_clients:
        _jwk_clients[jwks_uri] = PyJWKClient(jwks_uri)

    signing_key = _jwk_clients[jwks_uri].get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=config.client_id,
        issuer=config.issuer_url,
    )
    return claims


def extract_user_info(id_token_claims: dict) -> dict:
    """Extract user info (email, name, subject) from ID token claims."""
    return {
        "email": id_token_claims.get("email", ""),
        "name": id_token_claims.get("name", ""),
        "sub": id_token_claims.get("sub", ""),
    }
