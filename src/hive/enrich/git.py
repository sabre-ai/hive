"""Git enricher — attaches repository context to a session."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class GitEnricher:
    """Captures branch, HEAD SHA, remote URL, diff stat, and user name."""

    def name(self) -> str:
        return "git"

    # ── Eligibility ──────────────────────────────────────────────────

    def should_run(self, session: dict[str, Any]) -> bool:
        project_path = session.get("project_path")
        if not project_path:
            return False
        git_dir = Path(project_path) / ".git"
        return git_dir.is_dir()

    # ── Execution ────────────────────────────────────────────────────

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        project_path = session["project_path"]
        results: dict[str, Any] = {}

        commands: dict[str, list[str]] = {
            "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            "commit_sha": ["git", "rev-parse", "HEAD"],
            "remote_url": ["git", "config", "--get", "remote.origin.url"],
            "diff_stat": ["git", "diff", "--stat"],
            "user_name": ["git", "config", "user.name"],
        }

        for key, cmd in commands.items():
            output = self._git(cmd, cwd=project_path)
            if output is not None:
                results[key] = output

        return results

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _git(cmd: list[str], *, cwd: str) -> str | None:
        """Run a git command and return stripped stdout, or *None* on failure."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip() or None
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            log.debug("git command %s failed: %s", cmd, exc)
            return None
