# Quick Start

Get hive running in under a minute.

## Install

```bash
pipx install hive-team
```

!!! tip "From source"
    ```bash
    git clone https://github.com/sabre-ai/hive.git
    cd hive
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e .
    ```

## Choose Your Mode

=== "Solo Mode"

    Everything runs on one laptop. No server setup needed.

    ```bash
    cd your-project
    hive init
    hive serve
    ```

    Sessions are captured automatically as you use Claude Code. Ask Claude anything
    about your session history -- it reads from hive via MCP.

=== "Team Mode"

    One host runs the server. All developers point their config at that host.

    **On the server:**

    ```bash
    hive serve --port 3000
    ```

    **On each developer machine:**

    ```bash
    hive init
    hive config sharing on
    ```

    Set the server URL in `~/.config/hive/config.toml`:

    ```toml
    server_url = "http://team-server:3000"
    ```

    Every developer's sessions auto-push to the shared server. Every developer's
    Claude sees the team's collective history.

## Register the MCP Server

Register hive as an MCP server so Claude can access session history:

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

!!! info "Using a venv or pipx?"
    Pass the full path to the binary:
    ```bash
    claude mcp add --scope user --transport stdio hive -- /path/to/your/venv/bin/hive mcp
    ```

Start a new Claude Code session and run `/mcp` to verify -- you should see
`hive · connected`.

## Verify

```bash
hive log            # see captured sessions
hive search "auth"  # full-text search
hive stats          # aggregated metrics
```

!!! tip "Ask Claude directly"
    Once MCP is configured, Claude can search and analyze sessions for you:

    - *"What sessions touched the auth middleware this week?"*
    - *"Show me the conversation that led to the payment service refactor"*
    - *"How many tokens did the team use on the sabre-ai project?"*

## What `hive init` Does

Running `hive init` in a project directory will:

1. Create `~/.local/share/hive/` directory and SQLite database
2. Install Claude Code hooks into `.claude/settings.json`
3. Install a git `post-commit` hook (in git repos)
4. Ask whether to enable sharing to the team server
5. Backfill existing Claude Code session transcripts
6. Configure MCP server in Claude Code

!!! warning "Prerequisites"
    Python 3.11+ is required. For semantic search, you also need `uv` and
    [witchcraft](https://github.com/dropbox/witchcraft) model assets.

## Next Steps

- [Architecture Overview](../architecture/overview.md) -- understand how hive works
- [Configuration](../reference/configuration.md) -- customize settings
- [MCP Tools](../reference/mcp-tools.md) -- what Claude can do with hive
