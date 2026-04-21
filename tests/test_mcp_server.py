"""Tests for MCP server project scoping."""

from hive.mcp_server import _resolve_project


class TestResolveProject:
    def test_explicit_project_wins(self, monkeypatch):
        import hive.mcp_server as mod

        monkeypatch.setattr(mod, "_default_project", "/default/path")
        assert _resolve_project({"project": "/explicit"}) == "/explicit"

    def test_falls_back_to_default(self, monkeypatch):
        import hive.mcp_server as mod

        monkeypatch.setattr(mod, "_default_project", "/default/path")
        assert _resolve_project({}) == "/default/path"

    def test_all_projects_overrides_everything(self, monkeypatch):
        import hive.mcp_server as mod

        monkeypatch.setattr(mod, "_default_project", "/default/path")
        assert _resolve_project({"all_projects": True, "project": "/explicit"}) is None

    def test_all_projects_false_uses_default(self, monkeypatch):
        import hive.mcp_server as mod

        monkeypatch.setattr(mod, "_default_project", "/default/path")
        assert _resolve_project({"all_projects": False}) == "/default/path"

    def test_no_default_returns_none(self, monkeypatch):
        import hive.mcp_server as mod

        monkeypatch.setattr(mod, "_default_project", None)
        assert _resolve_project({}) is None
