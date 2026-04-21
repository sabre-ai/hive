# Solo Mode

Solo mode is hive running entirely on your local machine. Your SQLite database at `~/.local/share/hive/store.db` is the single source of truth -- no server, no network, no shared infrastructure.

## When to Use Solo Mode

Solo mode is the right choice when:

- You are an **individual developer** using Claude Code on your own projects
- You want **privacy-first** session capture with everything staying on disk
- You do not need to share session history with a team
- You want the **simplest setup** -- `hive init` and you are done

!!! note
    Solo mode is the default. If your `server_url` points to `localhost` (which it does out of the box), you are in solo mode.

## Key Features

### Automatic Capture

After running `hive init` in a project, every Claude Code session is captured automatically via hooks. No manual steps, no export commands. Sessions include the full conversation, git context, file paths, quality metrics, and token usage.

### Local Search

Search your entire history from the command line:

```bash
hive search "authentication bug"
```

Hive supports FTS5 keyword search out of the box. Install the search extras (`pip install "hive-team[search]"`) for semantic search powered by sqlite-vec.

### MCP Integration

Register the hive MCP server and Claude Code gains access to your full session history:

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

In solo mode, the MCP server reads directly from your local database using `LocalBackend`. No `hive serve` process is needed.

### File Lineage

Track how files evolved across AI-assisted sessions:

```bash
hive lineage src/auth.py
```

This shows every session that touched the file, along with related commits and the relationship type (created, modified, read).

## How It Works

1. `hive init` installs hooks into `.claude/settings.json` and a git post-commit hook
2. When you use Claude Code, hooks fire on session start, tool use, compaction, and stop
3. Each event is captured by the `ClaudeCodeAdapter`, enriched with git/file/quality context, and written to `store.db`
4. CLI commands (`hive log`, `hive search`, `hive show`) query the local database via `QueryAPI`
5. The MCP server uses the same `QueryAPI` through `LocalBackend`, giving Claude direct read access

## Subpages

- [Workflow](workflow.md) -- day-to-day patterns for solo use
- [Searching Your History](searching-your-history.md) -- CLI search, FTS5 syntax, search backends
- [Asking Claude](asking-claude.md) -- MCP setup and prompt examples
