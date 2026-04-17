# Configuration

hive uses two levels of configuration: a global config for the tool itself, and per-project configs for sharing behavior.

## Global Config

**Path**: `~/.hive/config.toml`

Created automatically by `hive init` if it does not exist. All fields are optional -- defaults are used when omitted.

```toml
# Directory where Claude Code stores session transcripts.
# Default: ~/.claude/projects
watch_path = "~/.claude/projects/"

# Path to the local SQLite database.
# Default: ~/.hive/store.db
db_path = "~/.hive/store.db"

# Path to the team server SQLite database.
# Default: ~/.hive/server.db
server_db_path = "~/.hive/server.db"

# URL of the team server for pushing sessions and MCP reads.
# Default: http://localhost:3000
server_url = "http://localhost:3000"

# Port the team server listens on.
# Default: 3000
server_port = 3000

# Time window (in minutes) for linking git commits to sessions.
# A post-commit hook looks for the most recently ended session
# within this window and creates an edge.
# Default: 30
link_window_minutes = 30

# Regex patterns for secret scrubbing. Matched strings are
# replaced with [REDACTED] before storage and before push.
# Default patterns cover: Stripe keys, GitHub PATs, AWS keys,
# Bearer tokens, and generic api_key/secret/token/password.
scrub_patterns = [
    'sk-[a-zA-Z0-9]{20,}',
    'ghp_[a-zA-Z0-9]{36,}',
    'AKIA[A-Z0-9]{16}',
    '[Bb]earer\s+[a-zA-Z0-9._\-]{20,}',
    '(?:api[_-]?key|secret|token|password)\s*[=:]\s*[\'"]?[a-zA-Z0-9._\-]{16,}',
]
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watch_path` | path | `~/.claude/projects` | Where Claude Code transcript `.jsonl` files live |
| `db_path` | path | `~/.hive/store.db` | Local SQLite database |
| `server_db_path` | path | `~/.hive/server.db` | Team server SQLite database |
| `server_url` | string | `http://localhost:3000` | Team server base URL (used by MCP and auto-push) |
| `server_port` | int | `3000` | Port for `hive serve` |
| `link_window_minutes` | int | `30` | Max age (minutes) of a session for commit linking |
| `scrub_patterns` | list[string] | (see above) | Regex patterns to redact from content |

## Per-Project Config

**Path**: `<project_root>/.hive/config.toml`

Controls whether sessions from this project are auto-pushed to the team server on the `Stop` hook.

```toml
# Enable or disable sharing to the team server.
# Accepts: "on", "off", true, false
sharing = "off"
```

### Managing Sharing

```bash
# Enable sharing for the current project
hive config sharing on

# Disable sharing
hive config sharing off

# Enable for a specific project directory
hive config sharing on --project /path/to/project
```

The `hive init` command also prompts for this during setup.

## Config Loading

The global config is loaded by `Config.load()` from `~/.hive/config.toml`. Per-project config is loaded by `load_project_config(project_path)` which reads `<project>/.hive/config.toml`. Both use TOML format and fall back to defaults when the file is missing or a field is absent.

**Source**: `src/hive/config.py`
