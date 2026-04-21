# Configuration

Hive uses TOML configuration files. For most users, running `hive init` creates sensible defaults and no manual editing is needed.

## Global Config

The global config lives at `~/.config/hive/config.toml`. It is created automatically by `hive init`.

```toml
# ~/.config/hive/config.toml

# Where Claude Code stores project data (usually the default is fine)
# watch_path = "~/.claude/projects/"

# Local database path
# db_path = "~/.local/share/hive/store.db"

# Team server URL (localhost = solo mode)
server_url = "http://localhost:3000"

# Server listen port (used by `hive serve`)
server_port = 3000
```

### Key Settings

| Setting | Default | Description |
|---|---|---|
| `server_url` | `http://localhost:3000` | Points to the team server. Localhost means solo mode. |
| `server_port` | `3000` | Port for `hive serve` to listen on. |
| `db_path` | `~/.local/share/hive/store.db` | Path to the local SQLite database. |
| `db_url` | `None` | SQLAlchemy database URL (overrides `db_path`). For future PostgreSQL/MySQL support. |
| `watch_path` | `~/.claude/projects/` | Where Claude Code stores session JSONL files. |

## Solo vs Team Mode

The `server_url` setting determines which mode hive operates in:

=== "Solo mode (default)"

    ```toml
    # Solo: everything stays local, no server needed
    server_url = "http://localhost:3000"
    ```

    The MCP server reads directly from your local `store.db`. No need to run `hive serve`.

=== "Team mode"

    ```toml
    # Team: point to the shared server
    server_url = "https://hive.your-company.com"
    ```

    Sessions are pushed to the team server. The MCP server proxies requests to the remote API.

!!! tip
    Hive detects solo mode automatically. If `server_url` points to `localhost`, `127.0.0.1`, or `::1`, it uses the local SQLite store directly.

## Per-Project Config

Each project can have its own config at `<project>/.hive/config.toml`. This file is meant to be committed to your repo so the whole team shares the same settings.

```toml
# myproject/.hive/config.toml

# Enable sharing sessions to the team server
sharing = "on"
```

Currently, the per-project config controls whether sessions from that project are pushed to the team server. The `hive init` command offers to set this up interactively.

## Search Backend

Hive defaults to `sqlite-vec` for search. You can configure it under the `[search]` section:

```toml
[search]
backend = "sqlite-vec"           # "sqlite-vec" or "witchcraft"
embedding_model = "all-MiniLM-L6-v2"  # Sentence-transformer model
# vec_db_path = "~/.local/share/hive/search_vec.db"
```

!!! note
    The `sqlite-vec` backend requires the search extras: `pip install "hive-team[search]"`. Without it, hive falls back to FTS5 full-text search, which still works well for keyword queries.

## Full Reference

For the complete list of all configuration options, including scrub patterns, search tuning, and advanced server settings, see [Reference > Configuration](../reference/configuration.md).
