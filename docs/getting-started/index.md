# Getting Started

This guide walks you through three stages. Each one builds on the last — stop at any point and you have a working setup.

## Stage 1: Solo Mode

Install hive and capture your first session. Everything stays on your local machine.

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Initialize hive in any project:

```bash
cd your-project
hive init
```

When prompted "Enable sharing to team server?", answer **N** — you can enable it later.

??? note "What `hive init` does"
    1. Creates `~/.local/share/hive/store.db` (SQLite database)
    2. Creates `~/.config/hive/config.toml` (default settings)
    3. Installs Claude Code hooks in `.claude/settings.json`
    4. Installs a git `post-commit` hook
    5. Backfills any existing Claude Code sessions

Now register hive as an MCP server so Claude can search your history:

```bash
claude mcp add --scope user --transport stdio hive -- /path/to/hive/.venv/bin/hive mcp
```

Restart Claude Code and verify with `/mcp` — you should see `hive` listed.

**Try it:**

```bash
hive log                          # see captured sessions
hive search "auth"                # full-text search
```

Or ask Claude directly:

```
> What did I work on today?
> Show me the session where I refactored the payment handler
```

You now have automatic session capture, local search, and Claude can query your entire coding history.

---

## Stage 2: Connect Claude Desktop

Sessions from Claude Desktop brainstorms become searchable alongside your Claude Code sessions.

Claude Desktop is sandboxed on macOS and cannot access `~/Documents/`. Install hive with pipx so the binary lives outside the sandbox:

```bash
pipx install /path/to/hive   # use the directory where you cloned hive
```

Then add hive as an MCP server in `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hive": {
      "command": "/Users/YOUR_USERNAME/.local/bin/hive",
      "args": ["mcp"]
    }
  }
}
```

!!! note "Picking up source changes"
    Since this is a non-editable install, re-run `pipx install --force /path/to/hive` after making source changes to update the Claude Desktop copy.

**Save a conversation:** At the end of a design discussion in Claude Desktop, say:

```
Save this conversation to hive
```

Claude calls the `capture_session` tool and the conversation is stored with source `claude_desktop`.

**Cross-tool lineage:** When Claude Code later references that design session during implementation, hive automatically links the two sessions. View the chain with:

```bash
hive lineage <session-id>
```

You now have unified history across Claude Code and Claude Desktop.

!!! tip "Team server access"
    Once you connect to a team server (Stage 3), Claude Desktop automatically searches team-wide history too — no extra MCP configuration needed. The `server_url` in your global config applies to both Claude Code and Claude Desktop.

---

## Stage 3: Team Server

Share sessions across your team so everyone's Claude can search the collective history.

### Option A: Docker (recommended)

The easiest way to run a production team server — one command starts PostgreSQL (with pgvector) and the hive server together:

```bash
git clone https://github.com/sabre-ai/hive.git && cd hive
docker compose up -d
```

The server is now running at `http://localhost:3000` backed by PostgreSQL with semantic search via pgvector.

### Option B: SQLite (simple)

For quick local testing or small teams, install from source and run:

```bash
hive serve --port 3000
```

!!! warning "No built-in auth in MVP"
    Run on a trusted network or behind an authenticating reverse proxy (OAuth2 Proxy, Tailscale, etc.).

**Connect each developer's machine:**

Set the server URL in `~/.config/hive/config.toml`:

```toml
server_url = "http://team-server:3000"
```

Enable sharing:

```bash
hive config sharing on
```

!!! note "First time installing hive?"
    If you haven't completed Stage 1, run these steps first:
    ```bash
    cd your-project
    hive init                                                  # say Y to sharing
    claude mcp add --scope user --transport stdio hive -- /path/to/hive/.venv/bin/hive mcp
    ```

Verify the connection:

```bash
curl -s http://team-server:3000/ | jq .status              # should print "ok"
hive log                                                    # see team sessions
```

Sessions auto-push to the server in the background. Secrets are scrubbed client-side before leaving the laptop.

**Backfill existing sessions:** If you already have local sessions from before connecting to the server, push them in one go:

```bash
hive push                          # push all local sessions
hive push --project your-project   # push only one project
hive push --dry-run                # preview what would be pushed
```

You now have shared, searchable AI coding history for your team.

---

## Troubleshooting

??? tip "`command not found: hive`"
    The binary is not on your `PATH`. With pipx, run `pipx ensurepath`. With pip:
    ```bash
    python -m site --user-base    # find the install prefix
    export PATH="$HOME/.local/bin:$PATH"
    ```

??? tip "`ModuleNotFoundError: No module named 'tomllib'`"
    You need Python 3.11+. Check with `python3 --version`.

??? tip "`sqlite3.OperationalError: no such module: fts5`"
    Your Python was built without FTS5. On Ubuntu: `sudo apt install libsqlite3-dev` and rebuild Python.

??? tip "Sessions not appearing on the team server"
    Run `hive config sharing on` and check `.hive/config.toml` has `sharing = "on"`. Verify the server URL with `curl`.

## Next Steps

- [Daily Workflow](../tutorials/workflow.md) — day-to-day patterns
- [Searching Your History](../tutorials/searching.md) — advanced search and FTS5 syntax
- [Asking Claude](../tutorials/asking-claude.md) — MCP tools and prompt examples
- [Sharing Controls](../tutorials/sharing-controls.md) — per-project sharing settings
- [Architecture Overview](../architecture/overview.md) — how hive works under the hood
