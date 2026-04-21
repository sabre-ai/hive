# Troubleshooting

Solutions to common problems with hive setup, session capture, and team mode.

## Hooks not firing

**Symptom**: Claude Code sessions complete but nothing appears in `hive log`.

**Fix**: Verify that hive hooks are registered in Claude Code's settings:

```bash
cat .claude/settings.json | jq '.hooks'
```

You should see hive commands in the `Stop` hook. If not, re-run:

```bash
hive init
```

Also confirm the `hive` binary is on your PATH:

```bash
which hive
```

If this returns nothing, the binary is not on PATH. With pipx:

```bash
pipx ensurepath
```

Then restart your terminal.

## Sessions not pushing to server

**Symptom**: Sessions appear in `hive log` locally but not on the team server.

**Checklist**:

1. **Sharing enabled?**
    ```bash
    cat .hive/config.toml
    ```
    Should show `sharing = "on"`. If not:
    ```bash
    hive config sharing on
    ```

2. **Server reachable?**
    ```bash
    curl -s http://team-server:3000/ | jq .status
    ```
    Should return `"ok"`. If not, check the server is running and the URL is correct in `~/.config/hive/config.toml`.

3. **Check debug logs** for push errors:
    ```bash
    HIVE_LOG_LEVEL=DEBUG hive push --since 1d
    ```

4. **Manual push** to force-send recent sessions:
    ```bash
    hive push --since 7d
    ```

## Search returns nothing

**Symptom**: `hive search "my query"` returns no results even though matching sessions exist.

**Fix**: Rebuild the search index:

```bash
hive reindex
```

If using semantic search, verify the search backend is running. Full-text search (FTS5) works without any external backend -- if FTS5 returns nothing, the sessions may not contain the search terms.

!!! tip "Check what is indexed"
    Use `hive log` to browse recent sessions and confirm they contain the text you are searching for.

## MCP shows disconnected

**Symptom**: Claude Code does not list hive in `/mcp`, or MCP tools fail.

**Checklist**:

=== "Solo mode"

    In solo mode, `hive serve` is **not** needed. MCP reads directly from the local `store.db`. Verify:
    ```bash
    claude mcp list
    ```
    If hive is missing, re-add it:
    ```bash
    claude mcp add --scope user --transport stdio hive -- hive mcp
    ```

=== "Team mode"

    In team mode, MCP connects to the team server. Verify:
    1. The server is running: `curl http://team-server:3000/`
    2. The MCP config points to the correct binary:
    ```bash
    claude mcp list
    ```
    Re-add if needed:
    ```bash
    claude mcp add --scope user --transport stdio hive -- hive mcp
    ```

Common cause: the path to the `hive` binary changed (e.g., after a Python environment update). Re-running the `claude mcp add` command fixes this.

## Secret scrubbing too aggressive

**Symptom**: Legitimate text is being replaced with `[REDACTED]` in pushed sessions.

**Fix**: Identify which pattern is matching and disable it:

```bash
# Test a string against the scrubber
python -c "
from hive.privacy import scrub
print(scrub('the text that gets redacted'))
"
```

Once you identify the pattern name (check `scrub_patterns.toml`), disable it:

```toml title="~/.config/hive/config.toml"
[scrub]
disabled_patterns = ["generic_api_key"]   # (1)!
```

1. Use the pattern name, not the regex. Find names in the `[category]` sections of `scrub_patterns.toml`.

## Database locked

**Symptom**: `sqlite3.OperationalError: database is locked`

**Cause**: Another process has the SQLite file open with a write lock. Common when a zombie `hive serve` process is still running.

**Fix**:

```bash
# Find hive processes
ps aux | grep "hive serve"

# Kill the zombie process
kill <PID>

# Restart cleanly
sudo systemctl restart hive   # if using systemd
```

If the problem persists, check for stale WAL files:

```bash
ls -la ~/.local/share/hive/server.db*
```

!!! warning "Do not delete WAL files while the server is running"
    The `-wal` and `-shm` files are part of SQLite's write-ahead log. Only delete them after stopping all processes that access the database.

## Common environment issues

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: hive` | Reinstall: `pip install -e ".[dev]"` or `pipx install hive-team` |
| Wrong Python version | Hive requires Python 3.11+. Check with `python --version`. |
| Config not loading | Verify config path: `~/.config/hive/config.toml` (follows `$XDG_CONFIG_HOME`) |
| Database in unexpected location | Check `$XDG_DATA_HOME`. Default is `~/.local/share/hive/`. |
