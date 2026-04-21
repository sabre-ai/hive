# CLI Reference

Every `hive` subcommand, grouped by role.

## Infrastructure Commands

Commands for setting up and running hive services.

---

### `hive init`

Set up hive for a project: creates the local database, installs Claude Code hooks, backfills existing sessions, and offers to configure MCP.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | `.` | Project directory to initialize |

```bash
# Initialize the current project
hive init

# Initialize a specific project
hive init --project ~/code/my-app
```

!!! tip
    Run `hive init` once per project. It is safe to re-run -- it will skip steps that are already done.

---

### `hive serve`

Start the team server. Listens on `0.0.0.0:PORT` and exposes the REST API and optional semantic search.

| Flag | Default | Description |
|------|---------|-------------|
| `--port PORT` | Config value or `3000` | Port to listen on |
| `--no-search` | Off | Disable the semantic search backend |

```bash
# Start on default port
hive serve

# Start on a custom port, no semantic search
hive serve --port 8080 --no-search
```

---

### `hive mcp`

Start the MCP server over stdio. Used by Claude Code and other MCP clients.

```bash
hive mcp
```

No flags. The server reads from stdin and writes to stdout using the MCP protocol.

---

### `hive capture <event_name>`

Ingest a session event. Called by Claude Code hooks -- you rarely call this directly. Reads JSON from stdin.

| Positional | Description |
|------------|-------------|
| `event_name` | One of: `session-start`, `stop`, `post-tool-use`, `pre-compact` |

```bash
# Typically called by hooks, but can be invoked manually
echo '{"session_id": "abc123", ...}' | hive capture stop
```

---

### `hive config sharing <on|off>`

Enable or disable automatic push of sessions to the team server.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | `.` | Target project directory |

```bash
# Enable auto-push for current project
hive config sharing on

# Disable for a specific project
hive config sharing off --project ~/code/my-app
```

---

## Developer Commands

Commands for browsing, searching, and managing sessions.

---

### `hive log`

List recent sessions, newest first.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | All projects | Filter by project |
| `-n, --count N` | `20` | Number of sessions to show |

```bash
# Last 20 sessions across all projects
hive log

# Last 5 sessions for a specific project
hive log --project ~/code/my-app -n 5
```

---

### `hive search <query>`

Full-text search across session content.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | All projects | Filter by project |
| `--author NAME` | All authors | Filter by author |
| `--since YYYY-MM-DD` | No limit | Sessions after this date |
| `--until YYYY-MM-DD` | No limit | Sessions before this date |

```bash
# Search for authentication-related sessions
hive search "auth middleware"

# Scoped search
hive search "database migration" --project ~/code/api --since 2025-01-01
```

---

### `hive show <session_id>`

Display a single session with its messages and metadata. Supports prefix matching -- the first 12 characters of a session ID are enough.

| Flag | Default | Description |
|------|---------|-------------|
| `--expand-tools` | Off | Show full tool message content |

```bash
# Show a session (prefix match)
hive show abc123def456

# Show with full tool output
hive show abc123def456 --expand-tools
```

---

### `hive lineage <file_path>`

Show all sessions and commits linked to a file. The path is resolved to an absolute path automatically.

```bash
hive lineage src/auth.py
```

---

### `hive projects`

List all known projects with their session counts.

```bash
hive projects
```

---

### `hive stats`

Aggregate statistics about sessions.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | All projects | Filter by project |
| `--since YYYY-MM-DD` | No limit | Sessions after this date |

```bash
# Stats for everything
hive stats

# Stats for one project since March
hive stats --project ~/code/api --since 2025-03-01
```

---

### `hive tag <session_id> <tag_value>`

Add a tag annotation to a session.

```bash
hive tag abc123def456 important
hive tag abc123def456 "needs-review"
```

---

### `hive delete <session_id>`

Delete a session and all related data (messages, enrichments, annotations, edges) from the local store.

```bash
hive delete abc123def456
```

!!! warning
    This is permanent. Deleted sessions cannot be recovered.

---

### `hive push`

Push local sessions to the team server.

| Flag | Default | Description |
|------|---------|-------------|
| `--project PATH` | All projects | Only push from this project |
| `--since YYYY-MM-DD` | No limit | Only sessions after this date |
| `--dry-run` | Off | Show what would be pushed without pushing |

```bash
# Push everything
hive push

# Preview what would be pushed
hive push --dry-run

# Push only recent sessions from one project
hive push --project ~/code/api --since 2025-04-01
```

---

### `hive reindex`

Rebuild the full-text search index from all sessions. Useful after manual database changes or upgrades.

```bash
hive reindex
```
