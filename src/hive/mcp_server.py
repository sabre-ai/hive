"""MCP server exposing hive data to AI assistants over stdio.

Routes queries per-project: shared projects go to the team server,
unshared projects read from the local SQLite store.  Falls back to
local when the team server is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Protocol

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from hive.config import Config, load_project_config

logger = logging.getLogger(__name__)

server = Server("hive")


# ── Backend protocol ──────────────────────────────────────────────


class HiveBackend(Protocol):
    """Unified interface used by the MCP handlers."""

    async def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
    ) -> list[dict]: ...

    async def get_session(
        self,
        session_id: str,
        detail: str | None = None,
        role: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict | None: ...

    async def lineage(self, file_path: str) -> list[dict]: ...

    async def session_lineage(self, session_id: str) -> list[dict]: ...

    async def recent(
        self,
        project: str | None = None,
        author: str | None = None,
        n: int = 10,
        sort_by: str | None = None,
        min_tokens: int | None = None,
        model: str | None = None,
        min_correction_rate: float | None = None,
    ) -> list[dict]: ...

    async def stats(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict | list[dict]: ...

    async def delete_session(self, session_id: str) -> dict: ...


# ── Local backend (solo mode) ────────────────────────────────────


class LocalBackend:
    """Reads directly from the local SQLite store via QueryAPI."""

    def __init__(self, config: Config):
        from hive.store.query import QueryAPI

        self._api = QueryAPI(config=config)

    async def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        return self._api.search_sessions(query, project=project, author=author, since=since)

    async def get_session(
        self,
        session_id: str,
        detail: str | None = None,
        role: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict | None:
        return self._api.get_session(
            session_id, detail=detail, role=role, msg_limit=limit, msg_offset=offset or 0
        )

    async def lineage(self, file_path: str) -> list[dict]:
        return self._api.get_lineage(file_path)

    async def session_lineage(self, session_id: str) -> list[dict]:
        return self._api.get_lineage(session_id, id_type="session")

    async def recent(
        self,
        project: str | None = None,
        author: str | None = None,
        n: int = 10,
        sort_by: str | None = None,
        min_tokens: int | None = None,
        model: str | None = None,
        min_correction_rate: float | None = None,
    ) -> list[dict]:
        return self._api.list_sessions(
            project=project,
            author=author,
            limit=n,
            sort_by=sort_by,
            min_tokens=min_tokens,
            model=model,
            min_correction_rate=min_correction_rate,
        )

    async def stats(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict | list[dict]:
        return self._api.get_stats(project=project, since=since, group_by=group_by)

    async def delete_session(self, session_id: str) -> dict:
        deleted = self._api.delete_session(session_id)
        if deleted:
            return {"deleted": session_id}
        return {"error": "Session not found"}


# ── Remote backend (team mode) ───────────────────────────────────


class RemoteBackend:
    """Async HTTP client that wraps the hive REST API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {"q": query}
        if project:
            params["project"] = project
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        return await self._get("/api/search", params=params)

    async def get_session(
        self,
        session_id: str,
        detail: str | None = None,
        role: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict | None:
        params: dict[str, str] = {}
        if detail:
            params["detail"] = detail
        if role:
            params["role"] = role
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        try:
            return await self._get(f"/api/sessions/{session_id}", params=params or None)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def lineage(self, file_path: str) -> list[dict]:
        return await self._get(f"/api/lineage/{file_path}")

    async def session_lineage(self, session_id: str) -> list[dict]:
        return await self._get(f"/api/lineage/session/{session_id}")

    async def recent(
        self,
        project: str | None = None,
        author: str | None = None,
        n: int = 10,
        sort_by: str | None = None,
        min_tokens: int | None = None,
        model: str | None = None,
        min_correction_rate: float | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {"limit": str(n)}
        if project:
            params["project"] = project
        if author:
            params["author"] = author
        if sort_by:
            params["sort_by"] = sort_by
        if min_tokens is not None:
            params["min_tokens"] = str(min_tokens)
        if model:
            params["model"] = model
        if min_correction_rate is not None:
            params["min_correction_rate"] = str(min_correction_rate)
        return await self._get("/api/sessions", params=params)

    async def stats(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict | list[dict]:
        params: dict[str, str] = {}
        if project:
            params["project"] = project
        if since:
            params["since"] = since
        if group_by:
            params["group_by"] = group_by
        return await self._get("/api/stats", params=params)

    async def delete_session(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(f"{self.base_url}/api/sessions/{session_id}")
            r.raise_for_status()
            return r.json()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base_url}{path}", params=params)
            r.raise_for_status()
            return r.json()


# ── Lazy init & per-project routing ────────────────────────────────

_local: LocalBackend | None = None
_remote: RemoteBackend | None = None
_default_project: str | None = None


def _ensure_backends() -> None:
    """Lazily initialize both backends."""
    global _local, _remote
    if _local is not None:
        return
    config = Config.load()
    _local = LocalBackend(config)
    if config.server_url:
        _remote = RemoteBackend(config.server_url)
        logger.info("MCP: team server configured at %s", config.server_url)
    else:
        logger.info("MCP: no team server configured, local-only mode")


def _resolve_project(arguments: dict[str, Any]) -> str | None:
    """Determine the project filter for a query.

    Priority: all_projects=True -> None, explicit project -> use it, else cwd.
    """
    if arguments.get("all_projects"):
        return None
    return arguments.get("project") or _default_project


def _get_backend_for_project(project: str | None) -> LocalBackend | RemoteBackend:
    """Pick backend based on project sharing config.

    Shared projects route to the team server; unshared projects stay local.
    """
    _ensure_backends()
    assert _local is not None

    if not project or not _remote:
        return _local

    project_config = load_project_config(Path(project))
    if project_config.sharing:
        return _remote

    return _local


def _json_response(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


# ── Tool catalogue ──────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="search",
        description=(
            "Full-text search across captured AI coding sessions. "
            "Scoped to the current project by default. "
            "Returns matching sessions with highlighted snippets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "project": {
                    "type": "string",
                    "description": "Filter by project path (defaults to current working directory).",
                },
                "all_projects": {
                    "type": "boolean",
                    "description": "Search across all projects instead of just the current one.",
                },
                "author": {"type": "string", "description": "Filter by author name."},
                "since": {"type": "string", "description": "ISO-8601 datetime lower bound."},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_session",
        description=(
            "Retrieve the complete data for a single session, including all "
            "messages, enrichments, and annotations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Unique session identifier."},
                "detail": {
                    "type": "string",
                    "description": "Level of detail: omit for summary, 'messages' to include conversation",
                },
                "role": {
                    "type": "string",
                    "description": "Filter messages by role: 'human', 'assistant', or 'tool'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max messages to return (requires detail='messages')",
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip first N messages (requires detail='messages')",
                },
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="lineage",
        description=(
            "Return the lineage graph for a file or session. For files: every session "
            "that read or modified it. For sessions: linked sessions, files, and commits."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or project-relative file path.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID to get lineage for (alternative to file_path).",
                },
            },
        },
    ),
    Tool(
        name="recent",
        description=(
            "List the most recent captured sessions. Scoped to the current project by default."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project path (defaults to current working directory).",
                },
                "all_projects": {
                    "type": "boolean",
                    "description": "Search across all projects instead of just the current one.",
                },
                "author": {"type": "string", "description": "Filter by author name."},
                "n": {
                    "type": "integer",
                    "description": "Number of sessions to return (default 10, max 100).",
                },
                "sort_by": {
                    "type": "string",
                    "description": "Sort by: 'tokens' (most expensive), 'corrections' (most corrections), 'messages' (longest)",
                },
                "min_tokens": {
                    "type": "integer",
                    "description": "Only sessions with at least this many tokens",
                },
                "model": {"type": "string", "description": "Filter by model name"},
                "min_correction_rate": {
                    "type": "number",
                    "description": "Only sessions with correction rate >= this (0.0 to 1.0)",
                },
            },
        },
    ),
    Tool(
        name="stats",
        description=(
            "Return aggregated statistics: total sessions, message counts, "
            "quality metrics, and date ranges. Scoped to the current project by default."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project path (defaults to current working directory).",
                },
                "all_projects": {
                    "type": "boolean",
                    "description": "Search across all projects instead of just the current one.",
                },
                "since": {"type": "string", "description": "ISO-8601 datetime lower bound."},
                "group_by": {
                    "type": "string",
                    "description": "Group results by: 'project', 'model', 'author', or 'week'",
                },
            },
        },
    ),
    Tool(
        name="delete",
        description="Delete a session and all its related data from the server.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to delete."},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="capture_session",
        description=(
            "Save the current conversation to hive. Call this when the user asks "
            "to save, capture, or preserve a design discussion, brainstorm, or any "
            "conversation worth keeping for future reference."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Brief title for this session."},
                "content": {
                    "type": "string",
                    "description": "The conversation content to save.",
                },
                "project": {
                    "type": "string",
                    "description": "Project path (defaults to current working directory).",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to categorize this session.",
                },
            },
            "required": ["title", "content"],
        },
    ),
    Tool(
        name="link_sessions",
        description=(
            "Create a lineage link between two sessions. Use this when you reference "
            "or build upon work from another session — especially when implementing a "
            "design from a claude_desktop session, or continuing work from a prior session."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "source_session_id": {
                    "type": "string",
                    "description": "The session being referenced (e.g. the design session).",
                },
                "target_session_id": {
                    "type": "string",
                    "description": "The session doing the referencing (e.g. the implementation session).",
                },
                "relationship": {
                    "type": "string",
                    "enum": ["implements", "continues", "references", "refines"],
                    "description": "How the sessions relate.",
                },
            },
            "required": ["source_session_id", "target_session_id", "relationship"],
        },
    ),
    Tool(
        name="current_session",
        description=(
            "Return the most recent hive session for the current project. "
            "Useful for getting the current session ID when creating links."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project path (defaults to current working directory).",
                },
            },
        },
    ),
]


# ── MCP handlers ────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    _ensure_backends()
    assert _local is not None
    project = _resolve_project(arguments)

    try:
        # ── Project-routed tools (shared → team server, else → local) ──

        if name == "search":
            backend = _get_backend_for_project(project)
            results = await backend.search(
                query=arguments["query"],
                project=project,
                author=arguments.get("author"),
                since=arguments.get("since"),
            )
            return _json_response(results)

        if name == "recent":
            backend = _get_backend_for_project(project)
            n = min(arguments.get("n", 10), 100)
            sessions = await backend.recent(
                project=project,
                author=arguments.get("author"),
                n=n,
                sort_by=arguments.get("sort_by"),
                min_tokens=arguments.get("min_tokens"),
                model=arguments.get("model"),
                min_correction_rate=arguments.get("min_correction_rate"),
            )
            return _json_response(sessions)

        if name == "stats":
            backend = _get_backend_for_project(project)
            stats = await backend.stats(
                project=project,
                since=arguments.get("since"),
                group_by=arguments.get("group_by"),
            )
            return _json_response(stats)

        if name == "current_session":
            backend = _get_backend_for_project(project)
            sessions = await backend.recent(project=project, n=1)
            if sessions:
                s = sessions[0]
                return _json_response(
                    {
                        "session_id": s["id"],
                        "source": s.get("source"),
                        "started_at": s.get("started_at"),
                        "summary": s.get("summary"),
                    }
                )
            return _json_response({"error": "No sessions found"})

        # ── Always-local tools ─────────────────────────────────────────

        if name == "get_session":
            session = await _local.get_session(
                session_id=arguments["session_id"],
                detail=arguments.get("detail"),
                role=arguments.get("role"),
                limit=arguments.get("limit"),
                offset=arguments.get("offset"),
            )
            # If not found locally and team server is available, try remote
            if session is None and _remote is not None:
                session = await _remote.get_session(
                    session_id=arguments["session_id"],
                    detail=arguments.get("detail"),
                    role=arguments.get("role"),
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset"),
                )
            if session is None:
                return _json_response({"error": "Session not found"})
            return _json_response(session)

        if name == "lineage":
            if "session_id" in arguments:
                edges = await _local.session_lineage(arguments["session_id"])
            else:
                edges = await _local.lineage(arguments["file_path"])
            return _json_response(edges)

        if name == "delete":
            result = await _local.delete_session(arguments["session_id"])
            return _json_response(result)

        if name == "capture_session":
            from hive.capture.claude_desktop import ClaudeDesktopAdapter

            adapter = ClaudeDesktopAdapter(skip_init=True)
            session_id = adapter._ingest(
                {
                    "title": arguments["title"],
                    "content": arguments["content"],
                    "project": project,
                    "tags": arguments.get("tags", []),
                }
            )
            return _json_response({"session_id": session_id, "status": "captured"})

        if name == "link_sessions":
            from hive.store.query import QueryAPI

            api = QueryAPI()
            api.insert_edge(
                "session",
                arguments["source_session_id"],
                "session",
                arguments["target_session_id"],
                arguments["relationship"],
            )
            return _json_response(
                {
                    "linked": True,
                    "source_session_id": arguments["source_session_id"],
                    "target_session_id": arguments["target_session_id"],
                    "relationship": arguments["relationship"],
                }
            )

    except httpx.ConnectError:
        # Team server unreachable — fall back to local for this request
        logger.warning("MCP: team server unreachable, falling back to local")
        return await _fallback_local(name, arguments, project)
    except httpx.HTTPStatusError as e:
        return _json_response(
            {"error": f"Server returned {e.response.status_code}: {e.response.text}"}
        )

    return _json_response({"error": f"Unknown tool: {name}"})


async def _fallback_local(
    name: str, arguments: dict[str, Any], project: str | None
) -> list[TextContent]:
    """Re-run a project-routed tool against the local backend."""
    assert _local is not None
    try:
        if name == "search":
            results = await _local.search(
                query=arguments["query"],
                project=project,
                author=arguments.get("author"),
                since=arguments.get("since"),
            )
            return _json_response(results)
        if name == "recent":
            n = min(arguments.get("n", 10), 100)
            sessions = await _local.recent(
                project=project,
                author=arguments.get("author"),
                n=n,
                sort_by=arguments.get("sort_by"),
                min_tokens=arguments.get("min_tokens"),
                model=arguments.get("model"),
                min_correction_rate=arguments.get("min_correction_rate"),
            )
            return _json_response(sessions)
        if name == "stats":
            stats = await _local.stats(
                project=project,
                since=arguments.get("since"),
                group_by=arguments.get("group_by"),
            )
            return _json_response(stats)
        if name == "current_session":
            sessions = await _local.recent(project=project, n=1)
            if sessions:
                s = sessions[0]
                return _json_response(
                    {
                        "session_id": s["id"],
                        "source": s.get("source"),
                        "started_at": s.get("started_at"),
                        "summary": s.get("summary"),
                    }
                )
            return _json_response({"error": "No sessions found"})
    except Exception:
        pass
    return _json_response({"error": "Cannot connect to hive server and local fallback failed."})


# ── Entry-point ─────────────────────────────────────────────────────


async def main() -> None:
    global _default_project
    _default_project = os.getcwd()
    logger.info("MCP: auto-detected project scope: %s", _default_project)

    from hive.store.db import init_db

    init_db()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
