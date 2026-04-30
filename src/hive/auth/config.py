"""Auth configuration — server-side OIDC settings and client-side token storage."""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field

from hive.config import DEFAULT_CONFIG_PATH, HIVE_CONFIG_DIR

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """Server-side authentication configuration."""

    enabled: bool = False
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    jwt_secret: str = ""
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 30
    allowed_domains: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, raw_config: dict | None = None) -> AuthConfig:
        """Load auth config from parsed TOML data and environment variables.

        ``raw_config`` should be the full parsed config dict (the ``[auth]``
        section is extracted automatically).
        """
        cfg = cls()
        auth_section = (raw_config or {}).get("auth", {})

        if "enabled" in auth_section:
            val = auth_section["enabled"]
            cfg.enabled = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        if "issuer_url" in auth_section:
            cfg.issuer_url = auth_section["issuer_url"]
        if "client_id" in auth_section:
            cfg.client_id = auth_section["client_id"]
        if "client_secret" in auth_section:
            cfg.client_secret = auth_section["client_secret"]
        if "scopes" in auth_section:
            cfg.scopes = auth_section["scopes"]
        if "jwt_secret" in auth_section:
            cfg.jwt_secret = auth_section["jwt_secret"]
        if "access_token_ttl_minutes" in auth_section:
            cfg.access_token_ttl_minutes = int(auth_section["access_token_ttl_minutes"])
        if "refresh_token_ttl_days" in auth_section:
            cfg.refresh_token_ttl_days = int(auth_section["refresh_token_ttl_days"])
        if "allowed_domains" in auth_section:
            cfg.allowed_domains = auth_section["allowed_domains"]

        # Environment variable overrides
        if env := os.environ.get("HIVE_AUTH_ENABLED"):
            cfg.enabled = env.lower() in ("true", "1", "yes")
        if env := os.environ.get("HIVE_AUTH_ISSUER_URL"):
            cfg.issuer_url = env
        if env := os.environ.get("HIVE_AUTH_CLIENT_ID"):
            cfg.client_id = env
        if env := os.environ.get("HIVE_AUTH_CLIENT_SECRET"):
            cfg.client_secret = env
        if env := os.environ.get("HIVE_AUTH_JWT_SECRET"):
            cfg.jwt_secret = env
        if env := os.environ.get("HIVE_AUTH_ALLOWED_DOMAINS"):
            cfg.allowed_domains = [d.strip() for d in env.split(",") if d.strip()]

        # Auto-generate JWT secret if auth is enabled but no secret set
        if cfg.enabled and not cfg.jwt_secret:
            cfg.jwt_secret = _generate_jwt_secret()

        return cfg


def _generate_jwt_secret() -> str:
    """Generate a random 256-bit JWT signing key and persist it."""
    import secrets

    secret = secrets.token_urlsafe(32)
    logger.warning("Auto-generated JWT secret. Set jwt_secret in config for production.")
    return secret


@dataclass
class AuthTokens:
    """Client-side tokens stored after login."""

    access_token: str = ""
    refresh_token: str = ""
    email: str = ""
    server: str = ""

    def is_valid(self) -> bool:
        return bool(self.access_token and self.refresh_token)


def load_auth_tokens() -> AuthTokens:
    """Read auth tokens from the global config file."""
    import sys

    if sys.version_info >= (3, 12):
        import tomllib
    else:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

    tokens = AuthTokens()
    if not DEFAULT_CONFIG_PATH.exists():
        return tokens

    with open(DEFAULT_CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)

    auth = data.get("auth", {})
    tokens.access_token = auth.get("access_token", "")
    tokens.refresh_token = auth.get("refresh_token", "")
    tokens.email = auth.get("email", "")
    tokens.server = auth.get("server", "")
    return tokens


def save_auth_tokens(tokens: AuthTokens) -> None:
    """Write auth tokens to the global config file with restricted permissions."""
    import sys

    if sys.version_info >= (3, 12):
        import tomllib
    else:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

    import tomli_w

    HIVE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if DEFAULT_CONFIG_PATH.exists():
        with open(DEFAULT_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)

    data["auth"] = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "email": tokens.email,
        "server": tokens.server,
    }

    with open(DEFAULT_CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)

    # Restrict file permissions to owner-only
    DEFAULT_CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def clear_auth_tokens() -> None:
    """Remove auth tokens from the global config file."""
    import sys

    if sys.version_info >= (3, 12):
        import tomllib
    else:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

    import tomli_w

    if not DEFAULT_CONFIG_PATH.exists():
        return

    with open(DEFAULT_CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)

    data.pop("auth", None)

    with open(DEFAULT_CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)
