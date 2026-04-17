# hive

Team server for Claude Code. Captures AI coding sessions from every developer's machine, pushes them to a shared server, and makes the team's collective history available to every user's Claude via MCP.

## Quick Start

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/sabre-ai/hive/main/install.sh | bash
```

This installs the Python package, builds the semantic search server, sets up Claude Code hooks, indexes your existing sessions, and starts the search backend as a persistent service. Requires `uv`, `cargo`, and a local clone of [witchcraft](https://github.com/dropbox/witchcraft) with model assets built (`make download`).

### Solo Mode (one laptop)

```bash
pip install hive-team   # or: pipx install hive-team
hive init          # install hooks, backfill existing sessions
hive serve         # start server on localhost:3000
```

Sessions are captured automatically as you use Claude Code. Ask Claude anything about your session history — it reads from hive via MCP.

### Team Mode (shared server)

```bash
# On the server:
hive serve --port 3000

# On each developer's machine:
# Set server_url in ~/.hive/config.toml:
#   server_url = "http://team-server:3000"
hive init
hive config sharing on

# Register MCP so Claude can query the team server:
claude mcp add --scope user --transport stdio hive -- hive mcp
```

Every developer's sessions auto-push to the shared server. Every developer's Claude sees the team's collective history.

## How It Works

```
Developer A                          Team Server
┌──────────────┐                    ┌──────────────┐
│ Claude Code  │                    │              │
│   hooks      │──► capture ──►     │  server.db   │
│              │    enrich          │              │
│              │    push ──────────►│  REST API    │
└──────────────┘                    │              │
                                    └──────┬───────┘
Developer B                               │
┌──────────────┐                          │
│ Claude Code  │──► capture ──► push ────►│
│              │                          │
│ Claude MCP   │◄──── reads from ─────────┘
└──────────────┘
```

Claude is the interface. The MCP server connects Claude to hive's REST API — same code path whether the server is on localhost or remote.

## Installation

### Prerequisites

- Python 3.11+

### From PyPI

```bash
pipx install hive-team
```

### From Source

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Setup

### `hive init`

Run once per project:

```bash
cd your-project
hive init
```

This will:

1. Create `~/.hive/` directory and SQLite database
2. Install Claude Code hooks into `.claude/settings.json`
3. Install a git `post-commit` hook (in git repos)
4. Ask whether to enable sharing to the team server
5. Backfill existing Claude Code session transcripts
6. Configure MCP server in Claude Code

### MCP Server Setup

Register hive as an MCP server so Claude can access your team's session history:

```bash
claude mcp add --transport stdio hive -- hive mcp
```

If you installed via pipx or a venv, use the full path to the binary:

```bash
claude mcp add --transport stdio hive -- /path/to/your/venv/bin/hive mcp
```

To make it available across all your projects (not just the current one):

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

Verify it's connected by starting a new Claude Code session and running `/mcp` — you should see `hive · connected`.

In team mode, the MCP server reads `server_url` from `~/.hive/config.toml`, so it automatically connects to whatever server you configured — no separate MCP setup needed.

Once configured, Claude can search, browse, and analyze all sessions on the server.

## Deployment Modes

### Solo Mode

Everything runs on one laptop. `hive serve` runs locally, hooks push to `localhost:3000`, MCP reads from `localhost:3000`.

```bash
hive init
hive serve
# Use Claude Code normally — sessions are captured and queryable via MCP
```

### Team Mode

One host runs `hive serve`. All developers point their config at that host.

**Server:**
```bash
hive serve --port 3000
```

**Each developer:**
```bash
# ~/.hive/config.toml
server_url = "http://team-server:3000"
```

```bash
hive init
hive config sharing on
```

The MCP server uses the same `server_url` from config, so Claude automatically queries the team server — no MCP reconfiguration needed.

Transitioning from solo to team is one config change — the `server_url`.

## Sharing and Privacy

### Project-Level Control

```bash
hive config sharing on    # enable auto-push for this project
hive config sharing off   # disable
```

Sharing is per-project. Stored in `<project>/.hive/config.toml`.

### Secret Scrubbing

All sessions are scrubbed before pushing to the server. Default patterns catch:
- API keys (`sk-`, `ghp_`, `AKIA`)
- Bearer tokens
- Generic secrets (`api_key=...`, `password=...`)
- Custom patterns from config

Secrets never leave the developer's machine.

### Session Deletion

Users can delete their sessions from the server at any time:

```bash
hive delete <session-id>
```

Or via Claude: *"delete my session about the client review"*

## MCP Tools (Primary Interface)

Claude is the UI. These tools are available to Claude when hive MCP is configured:

| Tool | Description | Required Args |
|------|-------------|---------------|
| `search` | Full-text search across team sessions | `query` |
| `get_session` | Retrieve complete session with messages | `session_id` |
| `lineage` | Sessions and commits connected to a file | `file_path` |
| `recent` | Latest sessions, filterable by project/author | — |
| `stats` | Quality metrics, token usage, patterns | — |
| `delete` | Remove a session from the server | `session_id` |

All tools accept optional `project`, `author`, and `since` filters. Responses are structured JSON — Claude decides what's relevant.

### Example Prompts

- *"What sessions touched the auth middleware this week?"*
- *"Show me the conversation that led to the payment service refactor"*
- *"How many tokens did the team use on the sabre-ai project?"*
- *"Which sessions had the most corrections?"*
- *"Delete my session from yesterday about the client review"*

## CLI Commands

### Infrastructure

| Command | Description |
|---------|-------------|
| `hive init` | Set up hooks, backfill, configure MCP |
| `hive serve` | Start the team server |
| `hive mcp` | Start the MCP server (stdio) |
| `hive config sharing on\|off` | Toggle auto-push for current project |
| `hive capture <event>` | Called by hooks (not for direct use) |

### Developer Testing

| Command | Description |
|---------|-------------|
| `hive log [-n count]` | Recent sessions |
| `hive search <query>` | Full-text search |
| `hive show <session-id>` | Render session in terminal |
| `hive lineage <file-path>` | File history through sessions |
| `hive stats` | Aggregated metrics |
| `hive projects` | List all known projects |
| `hive tag <session-id> <tag>` | Annotate a session |
| `hive delete <session-id>` | Delete a session |

## REST API

Served by `hive serve`. This is the push target for clients and the data source for MCP.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/api/sessions` | Push a session from a client |
| `GET` | `/api/sessions` | List sessions (params: `source`, `project`, `author`, `since`, `until`, `tag`, `limit`, `offset`) |
| `GET` | `/api/sessions/:id` | Full session with messages, enrichments, annotations |
| `DELETE` | `/api/sessions/:id` | Delete a session |
| `GET` | `/api/search` | Full-text search (params: `q`, `project`, `author`, `since`, `until`) |
| `GET` | `/api/lineage/:path` | Lineage graph for a file |
| `GET` | `/api/stats` | Aggregated statistics |
| `GET` | `/api/projects` | List projects with counts |
| `POST` | `/api/annotations` | Add tag, comment, or rating |

Interactive API docs at `/api/docs`.

## How Capture Works

### Claude Code Hooks

`hive init` installs four hooks into `.claude/settings.json`:

| Hook | When It Fires | What It Captures |
|------|---------------|------------------|
| **SessionStart** | Session begins | Git state (branch, commit, remote, author) |
| **Stop** | Claude finishes responding | Parses JSONL transcript, enriches, stores locally, auto-pushes to server |
| **PostToolUse** | After each tool call | File paths from Read/Write/Edit/Bash, stored as edges |
| **PreCompact** | Before context compaction | Full conversation snapshot |

### Auto-Push Flow

On every Stop hook, if sharing is enabled for the project:
1. Session is written to local `store.db`
2. Full payload is exported (session + messages + enrichments + edges)
3. Secrets are scrubbed
4. Payload is POSTed to the server (fire-and-forget, non-blocking)

### Git Post-Commit Hook

Links recently active sessions to commits and changed files. Installed in `.git/hooks/post-commit`.

## Enrichers

Enrichers run at capture time, attaching context to sessions:

| Enricher | Runs When | Captures |
|----------|-----------|----------|
| **Git** | Project is a git repo | branch, commit SHA, remote, diff stat, user.name |
| **Files** | Always | File paths from tool-use messages |
| **Quality** | Always | message count, human/assistant ratio, correction frequency, duration |
| **Tokens** | Always | input/output/cache tokens, model name |

### Adding Custom Enrichers

```python
from hive.enrich.base import Enricher

class MyEnricher(Enricher):
    def name(self) -> str:
        return "my_enricher"

    def should_run(self, session: dict) -> bool:
        return True

    def run(self, session: dict) -> dict[str, Any]:
        return {"my_key": "my_value"}
```

Register in `src/hive/enrich/__init__.py`. No schema changes needed.

## Configuration

### Global Config

`~/.hive/config.toml`:

```toml
# Team server URL (default: localhost for solo mode)
server_url = "http://localhost:3000"

# Server port
server_port = 3000

# Claude Code transcript location
watch_path = "~/.claude/projects/"

# Local database
db_path = "~/.hive/store.db"

# Server database (used by hive serve)
server_db_path = "~/.hive/server.db"

# Git hook commit linking window (minutes)
link_window_minutes = 30

# Secret scrubbing patterns
scrub_patterns = [
    "sk-[a-zA-Z0-9]{20,}",
    "ghp_[a-zA-Z0-9]{36,}",
    "AKIA[A-Z0-9]{16}",
]
```

### Per-Project Config

`<project>/.hive/config.toml`:

```toml
sharing = "on"   # or "off"
```

## File Layout

```
~/.hive/
├── store.db          # local sessions (capture writes here)
├── server.db         # pushed sessions (hive serve reads here)
├── config.toml       # global config
└── logs/

<project>/.hive/
└── config.toml       # project config (sharing on/off)

<project>/.claude/settings.json    # hooks installed by init
<project>/.git/hooks/post-commit   # installed by init
```

## Database

Two SQLite databases (same schema):

- `store.db` — local, all sessions captured on this machine
- `server.db` — used by `hive serve`, contains sessions pushed from all clients

| Table | Purpose |
|-------|---------|
| `sessions` | Session metadata (id, source, project, author, timestamps, summary) |
| `messages` | Individual messages (role, content, tool_name, ordinal, timestamp) |
| `enrichments` | Key-value context from enrichers (source, key, value) |
| `annotations` | User-applied metadata (tags, comments, ratings) |
| `edges` | Lineage graph (source_type/id &rarr; target_type/id + relationship) |
| `sessions_fts` | FTS5 full-text search index |

## Tech Stack

**Backend**: Python 3.11+, Click, FastAPI, SQLite (WAL mode), MCP SDK, httpx

## License

Apache-2.0
