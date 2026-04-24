# Solo Mode

Install hive and capture your first session. Everything stays on your local machine.

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

!!! warning "venv installs are terminal-specific"
    The `hive` command only works while the venv is active. Each new terminal
    needs `source /path/to/hive/.venv/bin/activate`. For a global install
    (works in all terminals), use `pipx install /path/to/hive` instead.

In hive, a **project** is any directory where you use Claude Code — typically a git repo. Claude Code already stores your session history per directory under `~/.claude/projects/`. Running `hive init` in a project directory imports that history into hive and installs hooks for automatic future capture.

```bash
cd your-project
hive init
```

When prompted "Enable sharing to team server?", answer **N** — you can enable it later in [Team Server](team-server.md).

??? note "What `hive init` does"
    1. Creates `~/.local/share/hive/store.db` (SQLite database)
    2. Creates `~/.config/hive/config.toml` (default settings)
    3. Installs Claude Code hooks in `.claude/settings.json`
    4. Installs a git `post-commit` hook
    5. Backfills **all** existing Claude Code sessions for this project — current and past

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

## Next Steps

- [Connect Claude Desktop](desktop.md) — unified history across Code and Desktop
- [Daily Workflow](../tutorials/workflow.md) — day-to-day patterns
- [Searching Your History](../tutorials/searching.md) — advanced search and FTS5 syntax
