# Getting Started

This guide walks you through three stages. Each one builds on the last — stop at any point and you have a working setup.

## Stage 1: Solo Mode

Install hive and capture your first session. Everything stays on your local machine.

=== "pipx (recommended)"

    ```bash
    pipx install hive-team
    ```

=== "From source"

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
claude mcp add --scope user --transport stdio hive -- hive mcp
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

Add hive as an MCP server in Claude Desktop by editing `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hive": {
      "command": "/Users/YOUR_USERNAME/.local/pipx/venvs/hive-team/bin/python",
      "args": ["-m", "hive.cli", "mcp"]
    }
  }
}
```

!!! warning "macOS sandbox"
    Claude Desktop is sandboxed and cannot access `~/Documents/`. Use a `pipx install` (not `pip install -e`) so hive lives under `~/.local/` which is accessible.

!!! tip "Find your pipx Python path"
    ```bash
    pipx environment --value PIPX_LOCAL_VENVS
    # typically: ~/.local/pipx/venvs
    ```

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

---

## Stage 3: Team Server

Share sessions across your team so everyone's Claude can search the collective history.

**Start the server** (on any machine your team can reach):

```bash
hive serve --port 3000
```

!!! warning "No built-in auth in MVP"
    Run on a trusted network or behind an authenticating reverse proxy (OAuth2 Proxy, Tailscale, etc.).

**Connect each developer's machine:**

```bash
pipx install hive-team
cd your-project
hive init                                                  # say Y to sharing
```

Set the server URL in `~/.config/hive/config.toml`:

```toml
server_url = "http://team-server:3000"
```

If sharing wasn't enabled during init:

```bash
hive config sharing on
```

Register MCP and verify:

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
curl -s http://team-server:3000/ | jq .status              # should print "ok"
hive log                                                    # see team sessions
```

Sessions auto-push to the server in the background. Secrets are scrubbed client-side before leaving the laptop.

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
