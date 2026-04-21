# Configuration

hive uses two levels of configuration: a global config for the tool itself, and per-project configs for sharing behavior.

## Global Config

**Path**: `~/.config/hive/config.toml`

Created automatically by `hive init` if it does not exist. All fields are optional -- defaults are used when omitted.

```toml
# Directory where Claude Code stores session transcripts.
watch_path = "~/.claude/projects/"

# Path to the local SQLite database.
db_path = "~/.local/share/hive/store.db"

# Path to the team server SQLite database.
server_db_path = "~/.local/share/hive/server.db"

# URL of the team server for pushing sessions and MCP reads.
server_url = "http://localhost:3000"

# Port the team server listens on.
server_port = 3000

# Time window (in minutes) for linking git commits to sessions.
link_window_minutes = 30

# SQLAlchemy database URL (overrides db_path). For future PostgreSQL/MySQL support.
# db_url = "sqlite:///~/.local/share/hive/store.db"
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watch_path` | path | `~/.claude/projects` | Where Claude Code transcript `.jsonl` files live |
| `db_path` | path | `~/.local/share/hive/store.db` | Local SQLite database |
| `server_db_path` | path | `~/.local/share/hive/server.db` | Team server SQLite database |
| `server_url` | string | `http://localhost:3000` | Team server base URL (used by MCP and auto-push) |
| `server_port` | int | `3000` | Port for `hive serve` |
| `link_window_minutes` | int | `30` | Max age (minutes) of a session for commit linking |
| `db_url` | string | `None` | SQLAlchemy database URL (overrides `db_path`). For future PostgreSQL/MySQL support. |

## Search Config

Search settings live under the `[search]` TOML section.

```toml
[search]
backend = "sqlite-vec"
url = "http://localhost:3033"
binary = "hive-search"
assets_path = "/path/to/witchcraft/assets"
vec_db_path = "~/.local/share/hive/search_vec.db"
embedding_model = "all-MiniLM-L6-v2"
```

### Search Field Reference

| TOML Key | Config Attribute | Default | Description |
|----------|-----------------|---------|-------------|
| `backend` | `search_backend` | `"sqlite-vec"` | Search backend: `"witchcraft"`, `"sqlite-vec"`, `"fts5-fallback"` |
| `url` | `search_url` | `"http://localhost:3033"` | URL of the witchcraft search server |
| `binary` | `search_binary` | `"hive-search"` | Path or name of the search binary |
| `assets_path` | `search_assets_path` | `None` | Path to witchcraft model assets |
| `vec_db_path` | `search_vec_db_path` | `"~/.local/share/hive/search_vec.db"` | SQLite-vec database for embeddings |
| `embedding_model` | `search_embedding_model` | `"all-MiniLM-L6-v2"` | Sentence-transformer model for embeddings |

!!! tip "Choosing a search backend"
    - **sqlite-vec**: Default. Uses local embeddings with sqlite-vec for
      vector similarity search. No external server needed.
    - **witchcraft**: Uses the witchcraft binary for semantic search.
      Requires model assets and a running search server.
    - **fts5-fallback**: Pure SQLite FTS5 keyword search. No dependencies,
      but no semantic understanding.

## Per-Project Config

**Path**: `<project_root>/.hive/config.toml`

Controls whether sessions from this project are auto-pushed to the team server on the `Stop` hook.

```toml
sharing = "on"   # or "off"
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

## Scrub Configuration

Secret scrubbing patterns are loaded from the built-in `scrub_patterns.toml` file shipped with hive. You can customize them in the `[scrub]` section of your global config.

### Default Pattern Categories

hive ships with 9 categories of secret patterns:

| Category | Examples |
|----------|----------|
| `ai_providers` | OpenAI keys (`sk-`), Anthropic keys (`sk-ant-`) |
| `cloud` | AWS access keys (`AKIA`), Google API keys (`AIza`) |
| `vcs_tokens` | GitHub PATs (`ghp_`), GitLab PATs (`glpat-`) |
| `auth_tokens` | Bearer tokens, Basic auth, Slack tokens, JWTs |
| `connection_strings` | MongoDB, PostgreSQL, Redis, AMQP URIs |
| `private_keys` | RSA/EC/DSA private key headers |
| `generic_secrets` | `api_key=...`, `password=...`, `secret_key=...` |
| `webhooks` | Slack and Discord webhook URLs |
| `env_vars` | Exported secrets like `AWS_SECRET_KEY=...` |

### Customizing Scrub Patterns

```toml
[scrub]
# Disable specific named patterns from the defaults
disabled_patterns = ["jwt", "basic_auth"]

# Add your own regex patterns
extra_patterns = [
    'my-internal-token-[a-zA-Z0-9]{32}',
    'CUSTOM_SECRET_[A-Z0-9]{20,}',
]
```

!!! warning "Client-side scrubbing"
    All scrubbing happens on the developer's machine **before** data is pushed
    to the team server. Secrets never leave the local machine.

## Config Loading

The global config is loaded by `Config.load()` from `~/.config/hive/config.toml`. Per-project config is loaded by `load_project_config(project_path)` which reads `<project>/.hive/config.toml`. Both use TOML format and fall back to defaults when the file is missing or a field is absent.

**Source**: `src/hive/config.py`
