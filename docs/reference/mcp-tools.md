# MCP Server Reference

The hive MCP server exposes session data to AI assistants over the stdio transport.

**Source**: `src/hive/mcp_server.py`

!!! note "Solo vs Team mode"
    In solo mode (`server_url` points to localhost), the MCP server reads
    directly from local SQLite -- no running `hive serve` required. In team
    mode it proxies to the remote REST API.

## Setup

=== "Claude Code"

    ```bash
    claude mcp add --scope user --transport stdio hive -- hive mcp
    ```

    If using a venv or pipx, use the full path to the binary:

    ```bash
    claude mcp add --scope user --transport stdio hive -- /path/to/venv/bin/hive mcp
    ```

    Start a new Claude Code session and run `/mcp` to verify -- you should see `hive · connected`.

=== "Claude Desktop"

    Claude Desktop is sandboxed on macOS and cannot access `~/Documents/`. Install hive with pipx so the binary lives outside the sandbox:

    ```bash
    pipx install /path/to/hive   # use the directory where you cloned hive
    ```

    Then add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

    ```json
    {
      "mcpServers": {
        "hive": {
          "command": "~/.local/pipx/venvs/hive-team/bin/python",
          "args": ["-m", "hive.cli", "mcp"]
        }
      }
    }
    ```

    Restart Claude Desktop. Re-run `pipx install --force /path/to/hive` after source changes to update the Claude Desktop copy.

## Tools

### search

Full-text search across all captured AI coding sessions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query (FTS5 syntax supported) |
| `project` | string | no | Filter by project path substring |
| `author` | string | no | Filter by author name |
| `since` | string | no | ISO-8601 datetime lower bound |

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

Retrieve session data with optional message filtering.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Unique session identifier |
| `detail` | string | no | Omit for summary, `"messages"` for full conversation |
| `role` | string | no | Filter messages by role: `"human"`, `"assistant"`, `"tool"` |
| `limit` | integer | no | Maximum number of messages to return |
| `offset` | integer | no | Skip this many messages (for pagination) |

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

!!! tip "Use `detail` and `role` to reduce payload size"
    Omit `detail` to get just the session summary without messages. Use
    `role = "human"` to see only user prompts, or `role = "assistant"` to
    see only Claude's responses.

Returns `{"error": "Session not found"}` if the ID does not exist.

### lineage

Return the lineage graph for a file or session. For files: every session that read or modified it. For sessions: linked sessions, files, and commits.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | no | Absolute or project-relative file path |
| `session_id` | string | no | Session ID to get lineage for (alternative to file_path) |

Provide either `file_path` or `session_id`.

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

List the most recent captured sessions with optional filtering and sorting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | no | Filter by project path substring |
| `author` | string | no | Filter by author name |
| `n` | integer | no | Number of sessions to return (default 10, max 100) |
| `sort_by` | string | no | Sort by: `"tokens"`, `"corrections"`, `"messages"` |
| `min_tokens` | integer | no | Minimum total token count |
| `model` | string | no | Filter by model identifier |
| `min_correction_rate` | number | no | Minimum correction frequency (0.0-1.0) |

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

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | no | Filter by project path substring |
| `since` | string | no | ISO-8601 datetime lower bound |
| `group_by` | string | no | Group results by: `"project"`, `"model"`, `"author"`, `"week"` |

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

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to delete |

```json
{"status": "ok", "session_id": "abc123-..."}
```

Returns a 404 error if the session does not exist.

### capture_session

Save a conversation to hive. Designed for use from Claude Desktop -- when the user asks to save or capture a discussion, Claude calls this tool.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | yes | Brief title for this session |
| `content` | string | yes | The conversation content to save |
| `project` | string | no | Project path this relates to |
| `tags` | array of strings | no | Tags to categorize this session |

```json
{"session_id": "4f1b6d28-...", "status": "captured"}
```

Sessions captured this way have `source = "claude_desktop"`.

### link_sessions

Create a lineage link between two sessions. Use this when referencing or building upon work from another session -- especially when implementing a design from a Claude Desktop session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_session_id` | string | yes | The session being referenced (e.g. the design session) |
| `target_session_id` | string | yes | The session doing the referencing (e.g. the implementation session) |
| `relationship` | string | yes | One of: `"implements"`, `"continues"`, `"references"`, `"refines"` |

```json
{"linked": true, "source_session_id": "...", "target_session_id": "...", "relationship": "implements"}
```

### current_session

Return the most recent hive session for the current project. Useful for getting the current session ID when creating links.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | no | Project path (defaults to current working directory) |

```json
{"session_id": "abc123-...", "source": "claude_code", "started_at": "2026-04-20T14:30:00", "summary": "..."}
```

## Common Filters

All tools accept optional `project`, `author`, and `since` filters. Responses are structured JSON -- Claude decides what is relevant.

## Error Handling

All tools return JSON. On failure:

- **Server unreachable**: `{"error": "Cannot connect to hive server. Is 'hive serve' running?"}`
- **HTTP error**: `{"error": "Server returned 404: Session not found"}`
- **Unknown tool**: `{"error": "Unknown tool: foo"}`
