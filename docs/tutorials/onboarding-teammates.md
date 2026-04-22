# Onboarding Teammates

Each developer runs these steps once to connect to the team server and start sharing sessions.

## Prerequisites

- Python 3.11+
- Claude Code installed and working
- The team server URL (e.g., `http://team-server:3000`)

## Step-by-step setup

### 1. Install hive

=== "pipx (recommended)"

    ```bash
    pipx install hive-team
    ```

=== "pip"

    ```bash
    pip install hive-team
    ```

### 2. Set the server URL

Edit `~/.config/hive/config.toml` and point to the team server:

```toml title="~/.config/hive/config.toml"
server_url = "http://team-server:3000"   # (1)!
```

1. Replace `team-server` with your actual server hostname or IP.

### 3. Initialize your project

```bash
cd /path/to/your-project
hive init
```

This creates the local database, installs Claude Code hooks in `.claude/settings.json`, sets up the git post-commit hook, and asks whether to enable sharing.

### 4. Enable sharing

If you did not enable sharing during `hive init`, turn it on explicitly:

```bash
hive config sharing on
```

This writes `sharing = "on"` to `<project>/.hive/config.toml`. Sessions from this project will now auto-push to the team server.

### 5. Add the MCP server to Claude Code

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

This registers hive as an MCP tool provider. Claude Code can now search team history, look up sessions, and query file lineage directly.

### 6. Verify everything works

Run these checks to confirm the setup is correct:

```bash
# Check that hive can reach the server
curl -s http://team-server:3000/ | jq .status
```

Expected output:

```
"ok"
```

```bash
# Check local sessions (may be empty on first run)
hive log
```

```bash
# Check sharing is enabled for this project
cat .hive/config.toml
```

Expected output:

```toml
sharing = "on"
```

In Claude Code, run `/mcp` to list connected MCP servers. You should see `hive` in the list.

!!! tip "Backfill existing sessions"
    `hive init` automatically backfills sessions from existing Claude Code JSONL transcripts in `~/.claude/projects/`. If you had sessions before installing hive, they will appear in `hive log` after init.

## What happens next

Once setup is complete, the workflow is invisible:

1. You start a Claude Code session and work normally.
2. When the session ends, the Stop hook fires.
3. Hive captures the session, enriches it with git and file context, and stores it locally.
4. A background thread scrubs secrets and pushes the session to the team server.
5. Teammates can search your session via CLI (`hive search`), the API, or MCP tools in their own Claude Code.

## Troubleshooting

| Problem | Fix |
|---|---|
| `hive: command not found` | Ensure the install location is on your `PATH`. With pipx, run `pipx ensurepath`. |
| Server unreachable | Verify the URL with `curl`. Check firewall rules and VPN. |
| Sessions not appearing on server | Run `hive config sharing on` and check that `.hive/config.toml` has `sharing = "on"`. |
| MCP not connected | Re-run the `claude mcp add` command. Check `claude mcp list` for errors. |
