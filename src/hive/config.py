"""Configuration management for hive."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

logger = logging.getLogger(__name__)

HIVE_DIR = Path.home() / ".hive"
DEFAULT_DB_PATH = HIVE_DIR / "store.db"
DEFAULT_SERVER_DB_PATH = HIVE_DIR / "server.db"
DEFAULT_CONFIG_PATH = HIVE_DIR / "config.toml"
DEFAULT_WATCH_PATH = Path.home() / ".claude" / "projects"

# Shipped with the package
_DEFAULT_PATTERNS_FILE = Path(__file__).parent / "scrub_patterns.toml"


def _load_default_patterns() -> dict[str, str]:
    """Load the default named patterns from scrub_patterns.toml.

    Returns a flat dict of {name: regex_pattern}.
    """
    patterns: dict[str, str] = {}
    if not _DEFAULT_PATTERNS_FILE.exists():
        logger.warning("Default scrub patterns file not found: %s", _DEFAULT_PATTERNS_FILE)
        return patterns
    with open(_DEFAULT_PATTERNS_FILE, "rb") as f:
        data = tomllib.load(f)
    for category in data.values():
        if isinstance(category, dict):
            for name, regex in category.items():
                if isinstance(regex, str):
                    patterns[name] = regex
    return patterns


def _load_scrub_patterns(user_config: dict | None = None) -> list[str]:
    """Build the final scrub pattern list.

    1. Load defaults from scrub_patterns.toml
    2. Remove any patterns listed in user's [scrub].disabled_patterns
    3. Append any patterns from user's [scrub].extra_patterns
    """
    named = _load_default_patterns()

    if user_config:
        scrub_section = user_config.get("scrub", {})

        # Remove disabled patterns by name
        disabled = scrub_section.get("disabled_patterns", [])
        if isinstance(disabled, list):
            for name in disabled:
                if name in named:
                    del named[name]

        # Start with remaining defaults
        patterns = list(named.values())

        # Append user's extra patterns
        extra = scrub_section.get("extra_patterns", [])
        if isinstance(extra, list):
            patterns.extend(extra)
    else:
        patterns = list(named.values())

    return patterns


@dataclass
class Config:
    watch_path: Path = field(default_factory=lambda: DEFAULT_WATCH_PATH)
    db_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)
    server_db_path: Path = field(default_factory=lambda: DEFAULT_SERVER_DB_PATH)
    server_url: str = "http://localhost:3000"
    server_port: int = 3000
    link_window_minutes: int = 30
    scrub_patterns: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> Config:
        config = cls()
        user_data: dict | None = None
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH, "rb") as f:
                user_data = tomllib.load(f)
            if "watch_path" in user_data:
                config.watch_path = Path(user_data["watch_path"])
            if "db_path" in user_data:
                config.db_path = Path(user_data["db_path"])
            if "server_db_path" in user_data:
                config.server_db_path = Path(user_data["server_db_path"])
            if "server_url" in user_data:
                config.server_url = user_data["server_url"]
            if "server_port" in user_data:
                config.server_port = user_data["server_port"]
            if "link_window_minutes" in user_data:
                config.link_window_minutes = user_data["link_window_minutes"]

        # Load scrub patterns from default file + user overrides
        config.scrub_patterns = _load_scrub_patterns(user_data)
        return config


@dataclass
class ProjectConfig:
    sharing: bool = False


def load_project_config(project_path: Path) -> ProjectConfig:
    """Load per-project config from <project>/.hive/config.toml."""
    config_file = project_path / ".hive" / "config.toml"
    if not config_file.exists():
        return ProjectConfig()
    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        sharing_val = data.get("sharing", False)
        if isinstance(sharing_val, str):
            sharing = sharing_val.lower() in ("on", "true", "yes", "1")
        else:
            sharing = bool(sharing_val)
        return ProjectConfig(sharing=sharing)
    except Exception:
        return ProjectConfig()


def save_project_config(project_path: Path, project_config: ProjectConfig) -> None:
    """Write per-project config to <project>/.hive/config.toml."""
    config_dir = project_path / ".hive"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    data = {"sharing": "on" if project_config.sharing else "off"}
    with open(config_file, "wb") as f:
        tomli_w.dump(data, f)
