# MCP Server Reference

The hive MCP server exposes session data to AI assistants over the stdio transport. It reads from the hive REST API (not SQLite directly), so it works against both localhost (solo mode) and a remote team server.

**Source**: `src/hive/mcp_server.py`

## Setup

Register hive as an MCP server with Claude Code:

```bash
claude mcp add --transport stdio hive -- hive mcp
```

If using a venv or pipx, use the full path to the binary:

```bash
claude mcp add --transport stdio hive -- /path/to/venv/bin/hive mcp
```

To make it available across all projects:

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

Start a new Claude Code session and run `/mcp` to verify — you should see `hive · connected`.

The MCP server requires `hive serve` to be running (it makes HTTP calls to the REST API at the configured `server_url`, default `http://localhost:3000`).

## Tools

### search

Full-text search across all captured AI coding sessions.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query (FTS5 syntax supported) |
| `project` | string | no | Filter by project path substring |
| `author` | string | no | Filter by author name |
| `since` | string | no | ISO-8601 datetime lower bound |

**Example output**:

```json
[
  {
    "id": "abc123-...",
    "source": "claude_code",
    "project_path": "/home/user/myproject",
    "author": "Alice",
    "started_at": "2026-04-10T14:30:00+00:00",
    "summary": "Refactor the authentication module",
    "snippet": "...moved the <mark>auth handler</mark> to a separate file..."
  }
]
```

### get_session

Retrieve the complete data for a single session, including all messages, enrichments, and annotations.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Unique session identifier |

**Example output**:

```json
{
  "id": "abc123-...",
  "source": "claude_code",
  "project_path": "/home/user/myproject",
  "author": "Alice",
  "started_at": "2026-04-10T14:30:00+00:00",
  "ended_at": "2026-04-10T15:10:00+00:00",
  "message_count": 24,
  "summary": "Refactor the authentication module",
  "messages": [
    {"ordinal": 1, "role": "human", "content": "...", "tool_name": null}
  ],
  "enrichments": [
    {"source": "git", "key": "branch", "value": "feature/auth"}
  ],
  "annotations": [
    {"type": "tag", "value": "refactor", "author": "user"}
  ]
}
```

Returns `{"error": "Session not found"}` if the ID does not exist.

### lineage

Return the lineage graph for a file -- every session that read or modified it, along with related commits.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | yes | Absolute or project-relative file path |

**Example output**:

```json
[
  {
    "session_id": "abc123-...",
    "summary": "Refactor auth handler",
    "started_at": "2026-04-10T14:30:00+00:00",
    "author": "Alice",
    "relationships": "touched,committed",
    "commit_shas": "a1b2c3d,e4f5g6h"
  }
]
```

### recent

List the most recent captured sessions, optionally filtered by project or author.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | no | Filter by project path substring |
| `author` | string | no | Filter by author name |
| `n` | integer | no | Number of sessions to return (default 10, max 100) |

**Example output**:

```json
[
  {
    "id": "abc123-...",
    "source": "claude_code",
    "project_path": "/home/user/myproject",
    "author": "Alice",
    "started_at": "2026-04-10T14:30:00+00:00",
    "message_count": 24,
    "summary": "Refactor the authentication module",
    "tags": "refactor,auth"
  }
]
```

### stats

Return aggregated statistics: total sessions, message counts, quality metrics, and date ranges.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | no | Filter by project path substring |
| `since` | string | no | ISO-8601 datetime lower bound |

**Example output**:

```json
{
  "total_sessions": 42,
  "total_messages": 1280,
  "avg_messages": 30.5,
  "earliest": "2026-03-01T09:00:00",
  "latest": "2026-04-14T16:30:00",
  "quality": {
    "correction_frequency": {"avg": 0.12, "total": 5.04},
    "human_assistant_ratio": {"avg": 0.85, "total": 35.7}
  }
}
```

### delete

Delete a session and all its related data from the server.

**Input schema**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to delete |

**Example output**:

```json
{"status": "ok", "session_id": "abc123-..."}
```

Returns a 404 error if the session does not exist.

## Error Handling

All tools return JSON. On failure:

- **Server unreachable**: `{"error": "Cannot connect to hive server. Is 'hive serve' running?"}`
- **HTTP error**: `{"error": "Server returned 404: Session not found"}`
- **Unknown tool**: `{"error": "Unknown tool: foo"}`
