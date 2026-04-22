"""Capture adapter for Claude Code hook events."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hive.capture.base import CaptureAdapter
from hive.config import Config
from hive.privacy import scrub
from hive.store.query import QueryAPI

logger = logging.getLogger(__name__)

# Tool names whose arguments contain file-path information.
_FILE_TOOLS = frozenset({"Read", "Write", "Edit", "Bash"})

# Events this adapter knows how to handle.
_KNOWN_EVENTS = frozenset({"SessionStart", "Stop", "PostToolUse", "PreCompact"})


class ClaudeCodeAdapter(CaptureAdapter):
    """Ingest Claude Code sessions via its hook system.

    Claude Code emits JSON on *stdin* for each hook event.  The JSON
    includes at minimum ``session_id`` and ``project_path``; some events
    also carry ``transcript_path`` or tool-use payloads.
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config.load()
        self._api = QueryAPI(self._config)

    # ── CaptureAdapter interface ─────────────────────────────────────

    def name(self) -> str:
        return "claude_code"

    def setup(self) -> None:
        """Ensure the watch path exists."""
        self._config.watch_path.mkdir(parents=True, exist_ok=True)

    def handle(self, event_name: str, data: dict) -> None:
        if event_name not in _KNOWN_EVENTS:
            logger.debug("Ignoring unknown event %s", event_name)
            return

        handler = {
            "SessionStart": self._on_session_start,
            "Stop": self._on_stop,
            "PostToolUse": self._on_post_tool_use,
            "PreCompact": self._on_pre_compact,
        }[event_name]

        try:
            handler(data)
        except Exception:
            logger.exception("Error handling %s for session %s", event_name, data.get("session_id"))

    # ── Event handlers ───────────────────────────────────────────────

    def _on_session_start(self, data: dict) -> None:
        """Record a brand-new session with git context."""
        session_id: str = data["session_id"]
        project_path: str = data.get("project_path", "")

        git = _collect_git_state(project_path) if project_path else {}
        now = datetime.now(UTC).isoformat()

        self._api.upsert_session(
            {
                "id": session_id,
                "source": self.name(),
                "project_path": project_path,
                "author": git.get("author", ""),
                "started_at": now,
                "ended_at": None,
                "message_count": 0,
                "summary": None,
            }
        )

        # Store git metadata as enrichments.
        for key in ("branch", "commit", "remote"):
            value = git.get(key)
            if value:
                self._api.insert_enrichment(session_id, "git", key, value)

    def _on_stop(self, data: dict) -> None:
        """Parse the session JSONL transcript and persist messages."""
        session_id: str = data["session_id"]
        transcript_path = self._resolve_transcript(data)

        if transcript_path is None or not transcript_path.exists():
            logger.warning("No transcript found for session %s", session_id)
            return

        messages = self._parse_jsonl(session_id, transcript_path)
        if not messages:
            return

        self._api.insert_messages(messages)

        # Build FTS content from all message text.
        fts_parts: list[str] = []
        for msg in messages:
            content = msg.get("content")
            if content:
                fts_parts.append(content)
        if fts_parts:
            self._api.index_session_fts(session_id, scrub("\n".join(fts_parts), self._config))

        summary = _derive_summary(messages)

        now = datetime.now(UTC).isoformat()
        self._api.upsert_session(
            {
                "id": session_id,
                "source": self.name(),
                "project_path": data.get("project_path", ""),
                "author": None,
                "started_at": None,
                "ended_at": now,
                "message_count": len(messages),
                "summary": summary,
            }
        )

        # Run enrichers
        from hive.enrich import run_enrichers

        session_data = {"project_path": data.get("project_path", ""), "messages": messages}
        run_enrichers(session_id, session_data, self._api)

        # Index in witchcraft search backend
        self._index_in_search(session_id, data, messages, summary)

        # Auto-push to server if sharing is enabled
        self._maybe_push(session_id, data.get("project_path", ""))

    def _on_post_tool_use(self, data: dict) -> None:
        """Extract file paths touched by tool calls and create edges."""
        session_id: str = data["session_id"]
        tool_name: str | None = data.get("tool_name")

        if tool_name not in _FILE_TOOLS:
            return

        file_paths = _extract_file_paths(tool_name, data.get("tool_input", {}))
        for fp in file_paths:
            try:
                self._api.insert_edge(
                    source_type="session",
                    source_id=session_id,
                    target_type="file",
                    target_id=fp,
                    relationship="touched",
                )
            except Exception:
                logger.debug("Duplicate edge session=%s file=%s (skipped)", session_id, fp)

    def _on_pre_compact(self, data: dict) -> None:
        """Snapshot the full conversation before Claude compacts it."""
        session_id: str = data["session_id"]
        transcript_path = self._resolve_transcript(data)

        if transcript_path is None or not transcript_path.exists():
            logger.warning("No transcript to snapshot for session %s", session_id)
            return

        try:
            raw = transcript_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning(
                "Could not read transcript for pre-compact snapshot: %s", transcript_path
            )
            return

        scrubbed = scrub(raw, self._config)
        self._api.insert_enrichment(session_id, "compact_snapshot", "transcript", scrubbed)

    def _maybe_push(self, session_id: str, project_path: str) -> None:
        """Push session to team server if sharing is enabled for this project."""
        if not project_path:
            return
        try:
            from hive.config import load_project_config

            project_config = load_project_config(Path(project_path))
            if not project_config.sharing:
                return

            payload = self._api.export_session(session_id)
            if not payload:
                return

            from hive.privacy import scrub_payload

            payload = scrub_payload(payload, self._config)

            import threading

            def _do_push():
                try:
                    import httpx

                    with httpx.Client(timeout=30) as client:
                        client.post(
                            f"{self._config.server_url}/api/sessions",
                            json=payload,
                        )
                except Exception:
                    logger.debug("Failed to push session %s to server", session_id)

            threading.Thread(target=_do_push, daemon=True).start()
        except Exception:
            logger.debug("Error in _maybe_push for session %s", session_id)

    def _index_in_search(
        self,
        session_id: str,
        data: dict,
        messages: list[dict[str, Any]],
        summary: str | None,
    ) -> None:
        """Push session into the search backend (best-effort)."""
        try:
            from hive.search import build_metadata, build_search_body, get_search_backend

            backend = get_search_backend(self._config)
            if not backend.is_available():
                return

            body, chunk_lengths = build_search_body(messages)
            if not body:
                return

            session = {
                "id": session_id,
                "project_path": data.get("project_path", ""),
                "author": data.get("author", ""),
                "source": self.name(),
                "started_at": data.get("started_at", ""),
                "summary": summary or "",
            }
            metadata = build_metadata(session)
            backend.add_document(
                session_id, session.get("started_at"), metadata, body, chunk_lengths
            )
            # Don't trigger_index here — embedding can be expensive.
            # Periodic indexing (via `hive reindex`) handles the rest.
        except Exception:
            logger.debug("Search backend indexing failed for session %s", session_id)

    # ── Backfill ─────────────────────────────────────────────────────

    def backfill(self, root: Path | None = None, project: Path | None = None) -> int:
        """Scan existing JSONL transcripts and import any unknown sessions.

        Parameters
        ----------
        root:
            Directory to scan.  Defaults to ``~/.claude/projects/``.
        project:
            If given, only import sessions whose working directory matches
            this project path.

        Returns
        -------
        int
            Number of sessions imported.
        """
        root = root or self._config.watch_path
        if not root.is_dir():
            logger.info("Watch path %s does not exist; nothing to backfill.", root)
            return 0

        project_filter = str(project.resolve()) if project else None

        imported = 0
        for jsonl_file in sorted(root.rglob("*.jsonl")):
            session_id = jsonl_file.stem
            # Skip subagent transcripts
            if "subagent" in str(jsonl_file) or "agent-" in session_id:
                continue
            existing = self._api.get_session(session_id)
            if existing is not None:
                continue

            meta = self._extract_metadata(jsonl_file)
            project_path = meta.get("cwd", str(jsonl_file.parent))

            # Skip sessions that don't belong to the requested project
            if project_filter and project_path != project_filter:
                continue
            messages = self._parse_jsonl(session_id, jsonl_file)
            if not messages:
                continue

            # Derive timestamps from the first and last message.
            started = messages[0].get("timestamp") or datetime.now(UTC).isoformat()
            ended = messages[-1].get("timestamp") or started

            summary = _derive_summary(messages)

            # Get author from git config in the project directory
            git = _collect_git_state(project_path) if project_path else {}
            author = git.get("author", "")

            self._api.upsert_session(
                {
                    "id": session_id,
                    "source": self.name(),
                    "project_path": project_path,
                    "author": author,
                    "started_at": started,
                    "ended_at": ended,
                    "message_count": len(messages),
                    "summary": summary,
                }
            )
            self._api.insert_messages(messages)

            fts_parts = [m["content"] for m in messages if m.get("content")]
            if fts_parts:
                self._api.index_session_fts(session_id, scrub("\n".join(fts_parts), self._config))

            # Create file edges from tool-use messages in the raw JSONL
            self._backfill_edges(session_id, jsonl_file)

            # Extract token usage
            self._extract_token_usage(session_id, jsonl_file)

            # Link commits that happened during this session
            self._backfill_commits(session_id, project_path, started, ended)

            # Run enrichers
            from hive.enrich import run_enrichers

            session_data = {"project_path": project_path, "messages": messages}
            run_enrichers(session_id, session_data, self._api)

            # Index in witchcraft search backend
            self._index_in_search(
                session_id,
                {"project_path": project_path, "author": author, "started_at": started},
                messages,
                summary,
            )

            imported += 1
            logger.info("Backfilled session %s (%d messages)", session_id, len(messages))

        return imported

    def _backfill_commits(
        self, session_id: str, project_path: str, started: str, ended: str
    ) -> None:
        """Find git commits made during a session's time window and create edges."""
        if not project_path or not Path(project_path).is_dir():
            return

        # Check if it's a git repo
        git_dir = Path(project_path) / ".git"
        if not git_dir.exists():
            # Walk up to find git root
            check = Path(project_path)
            while check != check.parent:
                if (check / ".git").exists():
                    project_path = str(check)
                    break
                check = check.parent
            else:
                return

        # Get commits between session start and end (+ 30 min buffer)
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--format=%H|%an",
                    f"--after={started}",
                    f"--before={ended}",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return

            for line in result.stdout.strip().splitlines():
                parts = line.strip().split("|", 1)
                if not parts:
                    continue
                commit_sha = parts[0]
                try:
                    self._api.insert_edge(
                        source_type="session",
                        source_id=session_id,
                        target_type="commit",
                        target_id=commit_sha,
                        relationship="produced",
                    )
                except Exception:
                    pass

                # Also link changed files from this commit
                files_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if files_result.returncode == 0:
                    for fp in files_result.stdout.strip().splitlines():
                        fp = fp.strip()
                        if fp:
                            abs_fp = str(Path(project_path) / fp)
                            try:
                                self._api.insert_edge(
                                    source_type="session",
                                    source_id=session_id,
                                    target_type="file",
                                    target_id=abs_fp,
                                    relationship="committed",
                                )
                            except Exception:
                                pass
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _extract_token_usage(self, session_id: str, path: Path) -> None:
        """Sum token usage from assistant message.usage fields and store as enrichments."""
        totals: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        model: str | None = None

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("type") != "assistant":
                continue

            message = record.get("message", {})
            if not model and message.get("model"):
                model = message["model"]

            usage = message.get("usage", {})
            if not usage:
                continue

            for key in totals:
                totals[key] += usage.get(key, 0)

        # Store as enrichments
        total_tokens = (
            totals["input_tokens"]
            + totals["output_tokens"]
            + totals["cache_read_input_tokens"]
            + totals["cache_creation_input_tokens"]
        )
        if total_tokens > 0:
            for key, value in totals.items():
                self._api.insert_enrichment(session_id, "tokens", key, str(value))
            self._api.insert_enrichment(session_id, "tokens", "total_tokens", str(total_tokens))
        if model:
            self._api.insert_enrichment(session_id, "tokens", "model", model)

    def _backfill_edges(self, session_id: str, path: Path) -> None:
        """Scan JSONL for tool_use blocks and create file edges retroactively."""
        seen_files: set[str] = set()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("type") != "assistant":
                continue

            message = record.get("message", {})
            content = message.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                if not isinstance(tool_input, dict):
                    continue

                file_paths = _extract_file_paths(tool_name, tool_input)
                for fp in file_paths:
                    if fp in seen_files:
                        continue
                    seen_files.add(fp)
                    try:
                        self._api.insert_edge(
                            source_type="session",
                            source_id=session_id,
                            target_type="file",
                            target_id=fp,
                            relationship="touched",
                        )
                    except Exception:
                        pass

    # ── Internal helpers ─────────────────────────────────────────────

    def _resolve_transcript(self, data: dict) -> Path | None:
        """Determine the path to the session's JSONL transcript file."""
        # Prefer explicit transcript_path from hook context.
        explicit = data.get("transcript_path")
        if explicit:
            return Path(explicit)

        # Fall back to convention: <watch_path>/<project_dir>/<session_id>.jsonl
        session_id = data.get("session_id")
        project_path = data.get("project_path")
        if session_id and project_path:
            # Claude stores transcripts under the watch_path, keyed by a
            # sanitised project directory name.
            project_dir = Path(project_path).name
            candidate = self._config.watch_path / project_dir / f"{session_id}.jsonl"
            if candidate.exists():
                return candidate

        return None

    def _parse_jsonl(self, session_id: str, path: Path) -> list[dict[str, Any]]:
        """Read a Claude Code JSONL transcript and return normalised messages.

        Real JSONL format per line::

            {
              "type": "user" | "assistant" | "progress" | "file-history-snapshot" | ...,
              "message": {"role": "user"|"assistant", "content": str | list},
              "isMeta": bool,
              "timestamp": "ISO-8601",
              "cwd": "/abs/project/path",
              "sessionId": "uuid",
              ...
            }
        """
        messages: list[dict[str, Any]] = []
        ordinal = 0

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.warning("Could not read transcript %s", path)
            return []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skipping malformed JSONL line in %s", path)
                continue

            # Skip non-message record types
            record_type = record.get("type", "")
            if record_type not in ("user", "assistant"):
                continue

            # Skip meta/system messages (hook outputs, command wrappers, etc.)
            if record.get("isMeta", False):
                continue

            # Extract the nested message
            message = record.get("message", {})
            role = _normalise_role(message.get("role", "") or record_type)
            if not role:
                continue

            content, tool_name = _extract_content(message)
            if content is None:
                continue

            ordinal += 1
            messages.append(
                {
                    "session_id": session_id,
                    "ordinal": ordinal,
                    "role": role,
                    "content": scrub(content, self._config),
                    "tool_name": tool_name,
                    "timestamp": record.get("timestamp"),
                }
            )

        return messages

    def _extract_metadata(self, path: Path) -> dict[str, str]:
        """Extract project path and other metadata from the first few JSONL lines."""
        meta: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("cwd") and "cwd" not in meta:
                        meta["cwd"] = record["cwd"]
                    if record.get("sessionId") and "sessionId" not in meta:
                        meta["sessionId"] = record["sessionId"]
                    if record.get("gitBranch") and "gitBranch" not in meta:
                        meta["gitBranch"] = record["gitBranch"]
                    if "cwd" in meta:
                        break  # Got what we need
        except OSError:
            pass
        return meta


# ── Pure helpers (module-level) ──────────────────────────────────────


def _derive_summary(messages: list[dict[str, Any]]) -> str | None:
    """Pick the first meaningful human message as the session summary.

    Skips messages that are just slash-commands, XML tags, tool results,
    or other system noise.
    """
    import re

    for msg in messages:
        if msg["role"] != "human":
            continue
        content = msg.get("content", "")
        if not content:
            continue
        # Skip XML-wrapped command messages
        if content.strip().startswith("<command-") or content.strip().startswith("<local-command"):
            continue
        # Skip tool_result messages (they contain tool_use_id refs)
        if "tool_use_id" in content and "tool_result" in content:
            continue
        # Skip messages that are just a slash command
        if re.match(r"^\s*<command-name>/", content):
            continue
        # Strip any leading XML tags that wrap user input
        cleaned = re.sub(r"<[^>]+>", "", content).strip()
        if not cleaned or len(cleaned) < 5:
            continue
        return cleaned[:120]
    return None


def _normalise_role(raw: str) -> str | None:
    """Map Claude Code transcript role strings to the DB enum."""
    mapping = {
        "human": "human",
        "user": "human",
        "assistant": "assistant",
        "tool": "tool",
        "tool_result": "tool",
        "tool_use": "tool",
    }
    return mapping.get(raw.lower())


def _extract_content(message: dict) -> tuple[str | None, str | None]:
    """Pull text and optional tool name from a message's content field.

    Returns (content_text, tool_name).
    """
    content = message.get("content")
    if content is None:
        return None, None

    # Content may be a plain string …
    if isinstance(content, str):
        return content, None

    # … or a list of content blocks (text, tool_use, tool_result, thinking).
    if isinstance(content, list):
        parts: list[str] = []
        tool_name: str | None = None
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append(str(text))
                elif block_type == "tool_use":
                    tool_name = block.get("name")
                    inp = block.get("input")
                    if isinstance(inp, dict):
                        # Show a compact summary of the tool call
                        parts.append(f"[{tool_name}]")
                    elif inp:
                        parts.append(str(inp))
                elif block_type == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str) and result_content:
                        parts.append(result_content)
                    elif isinstance(result_content, list):
                        for sub in result_content:
                            if isinstance(sub, dict) and sub.get("text"):
                                parts.append(sub["text"])
                # Skip "thinking" blocks — they're signatures, not content
        return ("\n".join(parts) if parts else None), tool_name

    return str(content), None


def _extract_file_paths(tool_name: str | None, tool_input: dict) -> list[str]:
    """Return file paths referenced by a tool-use payload."""
    paths: list[str] = []

    if tool_name == "Read" or tool_name == "Write" or tool_name == "Edit":
        fp = tool_input.get("file_path") or tool_input.get("path")
        if fp:
            paths.append(str(fp))

    elif tool_name == "Bash":
        # Best-effort: only extract absolute file paths from commands.
        command = tool_input.get("command", "")
        for token in command.split():
            cleaned = token.strip("\"'`;|&>()")
            # Only keep absolute paths that look like real files (have an extension
            # or are under common directories), skip redirections and URLs.
            if (
                cleaned.startswith("/")
                and not cleaned.startswith("//")
                and "://" not in cleaned
                and cleaned not in ("/", "/dev/null")
                and len(cleaned) > 3
                and not cleaned.endswith("/")
            ):
                paths.append(cleaned)

    # Also handle Glob and Grep tools
    elif tool_name in ("Glob", "Grep"):
        fp = tool_input.get("path")
        if fp:
            paths.append(str(fp))

    return paths


def _collect_git_state(project_path: str) -> dict[str, str]:
    """Gather current git metadata for *project_path*.

    Returns a dict with optional keys: branch, commit, remote, author.
    Failures are silently swallowed so that non-git projects still work.
    """
    result: dict[str, str] = {}

    commands = {
        "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "commit": ["git", "rev-parse", "HEAD"],
        "remote": ["git", "remote", "get-url", "origin"],
        "author": ["git", "config", "user.name"],
    }

    for key, cmd in commands.items():
        try:
            proc = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                result[key] = proc.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass

    return result
