"""Auth-aware HTTP client shared by CLI and MCP server.

Wraps httpx with automatic Bearer token injection and transparent
401 → refresh → retry logic.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from hive.auth.config import AuthTokens, load_auth_tokens, save_auth_tokens

logger = logging.getLogger(__name__)


class AuthenticatedClient:
    """HTTP client that attaches auth tokens and handles refresh."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._tokens: AuthTokens | None = None

    def _load_tokens(self) -> AuthTokens:
        if self._tokens is None:
            self._tokens = load_auth_tokens()
        return self._tokens

    def _auth_headers(self) -> dict[str, str]:
        tokens = self._load_tokens()
        if tokens.access_token:
            return {"Authorization": f"Bearer {tokens.access_token}"}
        return {}

    def _try_refresh(self) -> bool:
        """Attempt to refresh the access token. Returns True on success."""
        tokens = self._load_tokens()
        if not tokens.refresh_token:
            return False

        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(
                    f"{self.base_url}/auth/refresh",
                    json={"refresh_token": tokens.refresh_token},
                )
                if r.status_code != 200:
                    logger.warning("Token refresh failed: %s", r.status_code)
                    return False

                data = r.json()
                tokens.access_token = data["access_token"]
                tokens.refresh_token = data["refresh_token"]
                tokens.email = data.get("user", {}).get("email", tokens.email)
                save_auth_tokens(tokens)
                self._tokens = tokens
                return True
        except Exception as e:
            logger.warning("Token refresh error: %s", e)
            return False

    async def _async_try_refresh(self) -> bool:
        """Async version of refresh."""
        tokens = self._load_tokens()
        if not tokens.refresh_token:
            return False

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{self.base_url}/auth/refresh",
                    json={"refresh_token": tokens.refresh_token},
                )
                if r.status_code != 200:
                    logger.warning("Token refresh failed: %s", r.status_code)
                    return False

                data = r.json()
                tokens.access_token = data["access_token"]
                tokens.refresh_token = data["refresh_token"]
                tokens.email = data.get("user", {}).get("email", tokens.email)
                save_auth_tokens(tokens)
                self._tokens = tokens
                return True
        except Exception as e:
            logger.warning("Token refresh error: %s", e)
            return False

    # ── Sync methods (for CLI) ──────────────────────────────────────

    def sync_get(self, path: str, params: dict | None = None, timeout: int = 60) -> Any:
        """Sync GET with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, params=params, headers=self._auth_headers())
            if r.status_code == 401 and self._try_refresh():
                r = client.get(url, params=params, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()

    def sync_post(self, path: str, json: Any = None, timeout: int = 60) -> Any:
        """Sync POST with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=json, headers=self._auth_headers())
            if r.status_code == 401 and self._try_refresh():
                r = client.post(url, json=json, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()

    def sync_delete(self, path: str, timeout: int = 60) -> Any:
        """Sync DELETE with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=timeout) as client:
            r = client.delete(url, headers=self._auth_headers())
            if r.status_code == 401 and self._try_refresh():
                r = client.delete(url, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()

    # ── Async methods (for MCP server) ──────────────────────────────

    async def async_get(self, path: str, params: dict | None = None, timeout: int = 30) -> Any:
        """Async GET with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, params=params, headers=self._auth_headers())
            if r.status_code == 401 and await self._async_try_refresh():
                r = await client.get(url, params=params, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()

    async def async_post(self, path: str, json: Any = None, timeout: int = 30) -> Any:
        """Async POST with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=json, headers=self._auth_headers())
            if r.status_code == 401 and await self._async_try_refresh():
                r = await client.post(url, json=json, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()

    async def async_delete(self, path: str, timeout: int = 30) -> Any:
        """Async DELETE with automatic 401 retry."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.delete(url, headers=self._auth_headers())
            if r.status_code == 401 and await self._async_try_refresh():
                r = await client.delete(url, headers=self._auth_headers())
            r.raise_for_status()
            return r.json()
