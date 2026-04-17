"""Tests for hive.config module."""

from __future__ import annotations

from pathlib import Path

from hive.config import (
    Config,
    ProjectConfig,
    load_project_config,
    save_project_config,
)


class TestDefaultConfig:
    def test_default_config_values(self):
        cfg = Config()
        assert cfg.server_url == "http://localhost:3000"
        assert cfg.server_port == 3000
        assert cfg.link_window_minutes == 30
        assert isinstance(cfg.scrub_patterns, list)
        assert cfg.db_path.name == "store.db"
        assert cfg.server_db_path.name == "server.db"

    def test_loaded_config_has_scrub_patterns(self):
        cfg = Config.load()
        assert isinstance(cfg.scrub_patterns, list)
        assert len(cfg.scrub_patterns) >= 25


class TestProjectConfig:
    def test_project_config_save_and_load(self, tmp_path: Path):
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        # Save with sharing on
        save_project_config(project_dir, ProjectConfig(sharing=True))
        loaded = load_project_config(project_dir)
        assert loaded.sharing is True

        # Save with sharing off
        save_project_config(project_dir, ProjectConfig(sharing=False))
        loaded = load_project_config(project_dir)
        assert loaded.sharing is False

    def test_project_config_missing_file_returns_defaults(self, tmp_path: Path):
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()

        loaded = load_project_config(project_dir)
        assert loaded.sharing is False

    def test_project_config_creates_hive_dir(self, tmp_path: Path):
        project_dir = tmp_path / "newproject"
        project_dir.mkdir()

        save_project_config(project_dir, ProjectConfig(sharing=True))
        assert (project_dir / ".hive" / "config.toml").exists()
