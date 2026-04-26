# Quick Start

Install hive and capture your first session. Everything stays on your local machine.

## Install

```bash
curl https://sabre-ai.github.io/hive/install.sh | bash
```

This installs the hive CLI and configures the MCP server for both Claude Code and Claude Desktop (macOS).

??? note "What the installer does"
    1. Installs `uv` if not present
    2. Downloads and installs the hive Python package from the latest GitHub release
    3. Configures Claude Code MCP server (`claude mcp add`)
    4. Configures Claude Desktop MCP server (macOS only)
    5. Creates config at `~/.config/hive/config.toml`

## Enable capture for a project

In hive, a **project** is any directory where you use Claude Code — typically a git repo. Running `hive init` imports existing history and installs hooks for automatic future capture.

```bash
cd your-project
hive init
```

When prompted "Enable sharing to team server?", answer **N** — you can enable it later in [Team Server](team-server.md).

??? note "What `hive init` does"
    1. Creates `~/.local/share/hive/store.db` (SQLite database)
    2. Installs Claude Code hooks in `.claude/settings.json`
    3. Installs a git `post-commit` hook
    4. Backfills **all** existing Claude Code sessions for this project

Restart Claude Code and verify with `/mcp` — you should see `hive` listed.

## Try it

```bash
hive log                          # see captured sessions
hive search "auth"                # full-text search
```

Or ask Claude directly:

```
> What did I work on today?
> Show me the session where I refactored the payment handler
```

## Claude Desktop

Claude Code sessions are captured **automatically** via hooks. Claude Desktop has no hook system, so capture is **on demand** — you ask Claude to save conversations worth keeping.

To save a Desktop conversation:

```
Save this conversation to hive
```

Claude calls the `capture_session` MCP tool and the conversation is stored with source `claude_desktop`. When Claude Code later references that session, hive automatically links them. View the chain with:

```bash
hive lineage <session-id>
```

## Next Steps

- [Team Server](team-server.md) — share sessions across your team
- [Daily Workflow](../tutorials/workflow.md) — day-to-day patterns
- [Searching Your History](../tutorials/searching.md) — advanced search and FTS5 syntax
- [Asking Claude](../tutorials/asking-claude.md) — MCP tools and prompt examples
