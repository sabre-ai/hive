# Architecture

hive uses a four-layer pipeline to turn raw AI coding sessions into searchable, shareable team knowledge.

## Four-Layer Pipeline

```
Capture --> Enrich --> Store --> Serve

  Claude Code hooks         Git, Files,        SQLite + FTS5       MCP server
  (stdin JSON)              Quality enrichers  (store.db local)    REST API
  git post-commit hook                         (server.db team)    CLI
```

## Data Flow

```
+---------------------+
| Claude Code         |
| .claude/settings.json hooks:
|   SessionStart      |
|   Stop              |
|   PostToolUse       |
|   PreCompact        |
+--------+------------+
         | stdin JSON (session_id, project_path, transcript_path, ...)
         v
+--------+------------+
| Capture Layer       |
| ClaudeCodeAdapter   |
|  - parse JSONL      |
|  - scrub secrets    |
|  - extract files    |
|  - derive summary   |
+--------+------------+
         |
         v
+--------+------------+
| Enrich Layer        |
| GitEnricher         |  branch, commit, remote, diff_stat, user
| FilesEnricher       |  files_touched (from content + tool_use)
| QualityEnricher     |  message_count, ratio, corrections, duration
+--------+------------+
         |
         v
+--------+------------+       +-------------------+
| Store Layer         |       | Team Server       |
| ~/.hive/       |       | server.db         |
|   store.db (local)  +------>| REST API (FastAPI)|
|   SQLite + FTS5     | push  | /api/sessions     |
+--------+------------+       +--------+----------+
         |                             |
         v                             v
+--------+------------+       +--------+----------+
| Serve Layer         |       | MCP Server        |
| CLI (click + rich)  |       | reads from REST   |
|   search, show, log |       | stdio transport   |
|   lineage, stats    |       | 6 tools           |
+---------------------+       +-------------------+
```

## Solo vs Team Mode

**Solo mode** (default): Everything stays local. The CLI reads and writes `~/.hive/store.db` directly. The MCP server talks to `localhost:3000` which reads from `server.db`.

**Team mode**: Enable per-project sharing with `hive config sharing on`. When a session ends (`Stop` hook), the adapter scrubs secrets from the full payload and POSTs it to the configured `server_url` via a daemon thread. Team members run `hive serve` to host a shared server with its own `server.db`.

```
Developer A                          Team Server
store.db ---(auto-push on Stop)--->  server.db
                                         ^
Developer B                              |
store.db ---(auto-push on Stop)----------+
                                         |
MCP Server  <----(REST /api/...)--------+
```

## Two Databases

| Database | Path | Purpose |
|----------|------|---------|
| `store.db` | `~/.hive/store.db` | Local session data. Written by capture adapters and enrichers. Read by CLI commands. |
| `server.db` | `~/.hive/server.db` | Team server data. Written by the REST API `POST /api/sessions`. Read by the REST API and MCP server. |

Both use the same schema: `sessions`, `messages`, `enrichments`, `annotations`, `edges`, and `sessions_fts` (FTS5).

## Key Design Decisions

1. **Scrub on the client**: Secrets are redacted using regex patterns _before_ data leaves the local machine. The `scrub()` function runs during JSONL parsing (content) and again via `scrub_payload()` before any push to the server. Patterns are configurable in `config.toml`.

2. **MCP reads from REST, not SQLite**: The MCP server uses `httpx` to call the REST API rather than importing the SQLite layer. This means it works identically against localhost (solo) or a remote team server -- just change `server_url`.

3. **Daemon thread push**: Auto-push to the team server happens in a `threading.Thread(daemon=True)` so the Claude Code hook returns immediately. If the push fails, it is silently dropped (logged at debug level).

4. **Edges graph for lineage**: File and commit relationships are stored as typed edges (`session -> file`, `session -> commit`) rather than columns, enabling flexible lineage queries without schema changes.

5. **Idempotent setup**: `hive init` and all hook installations are safe to run repeatedly. Hooks check for existing entries before adding. Session import uses `ON CONFLICT` upserts and clears-then-reinserts for re-pushes.
