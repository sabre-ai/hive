"""MCP server exposing hive data to AI assistants over stdio.

Reads from the hive REST server (not SQLite directly), so it works
identically against localhost (solo mode) or a remote team server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from hive.config import Config

logger = logging.getLogger(__name__)

server = Server("hive")


# ── REST client ────────────────────────────────────────────────────


class ServerClient:
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
    ) -> dict:
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


# ── Lazy init ──────────────────────────────────────────────────────

_client: ServerClient | None = None


def _get_client() -> ServerClient:
    global _client
    if _client is None:
        config = Config.load()
        _client = ServerClient(config.server_url)
    return _client


def _json_response(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


# ── Tool catalogue ──────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="search",
        description=(
            "Full-text search across all captured AI coding sessions. "
            "Returns matching sessions with highlighted snippets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "project": {"type": "string", "description": "Filter by project path substring."},
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
            "Return the lineage graph for a file — every session that read "
            "or modified it, along with related commits."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or project-relative file path.",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="recent",
        description="List the most recent captured sessions, optionally filtered by project or author.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Filter by project path substring."},
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
            "quality metrics, and date ranges."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Filter by project path substring."},
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
]


# ── MCP handlers ────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    client = _get_client()

    try:
        if name == "search":
            results = await client.search(
                query=arguments["query"],
                project=arguments.get("project"),
                author=arguments.get("author"),
                since=arguments.get("since"),
            )
            return _json_response(results)

        if name == "get_session":
            session = await client.get_session(
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
            edges = await client.lineage(arguments["file_path"])
            return _json_response(edges)

        if name == "recent":
            n = min(arguments.get("n", 10), 100)
            sessions = await client.recent(
                project=arguments.get("project"),
                author=arguments.get("author"),
                n=n,
                sort_by=arguments.get("sort_by"),
                min_tokens=arguments.get("min_tokens"),
                model=arguments.get("model"),
                min_correction_rate=arguments.get("min_correction_rate"),
            )
            return _json_response(sessions)

        if name == "stats":
            stats = await client.stats(
                project=arguments.get("project"),
                since=arguments.get("since"),
                group_by=arguments.get("group_by"),
            )
            return _json_response(stats)

        if name == "delete":
            result = await client.delete_session(arguments["session_id"])
            return _json_response(result)

    except httpx.ConnectError:
        return _json_response({"error": "Cannot connect to hive server. Is 'hive serve' running?"})
    except httpx.HTTPStatusError as e:
        return _json_response(
            {"error": f"Server returned {e.response.status_code}: {e.response.text}"}
        )

    return _json_response({"error": f"Unknown tool: {name}"})


# ── Entry-point ─────────────────────────────────────────────────────


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
