# Solo Mode Workflow

A day-in-the-life guide for using hive as an individual developer. Everything stays local on your machine -- no server, no sharing, no setup beyond `hive init`.

## Morning: Pick Up Where You Left Off

Start your day by checking what happened in your last session:

```bash
hive log -n 5
```

```
a1b2c3d4e5f6  2026-04-19 17:45  claude-code (24 msgs)
  Refactor payment service to use Stripe API v2

b2c3d4e5f6a1  2026-04-19 14:20  claude-code (8 msgs)
  Fix auth middleware token refresh

c3d4e5f6a1b2  2026-04-19 10:05  claude-code (15 msgs)
  Add rate limiting to API endpoints
```

Need the full context from yesterday's refactor? Pull up the session:

```bash
hive show a1b2c3d4
```

Or ask Claude directly:

```
> What was the approach we took for the Stripe v2 migration yesterday?
```

## During the Day: Sessions Capture Automatically

Every time you use Claude Code, hive captures the session via hooks. You do not need to do anything -- no manual logging, no copy-paste, no export. The hooks fire on session start, tool use, compaction, and stop events.

Each captured session includes:

- The full conversation (human, assistant, and tool messages)
- Git context (branch, commit, remote, diff stats)
- File paths touched during the session
- Quality metrics (message counts, human/assistant ratio, corrections, duration)
- Token usage (input, output, cache)

## Check Your Stats

See aggregated statistics for your work:

```bash
hive stats
```

```
╭─── Session Statistics ───╮
│ Total sessions: 142       │
│ Total messages: 3,847     │
│ Avg messages/session: 27.1│
│ Date range: 2026-03-01 → 2026-04-20 │
╰──────────────────────────╯
```

Filter by project or date:

```bash
hive stats --project my-app --since 2026-04-14
```

## Search Your History

Find sessions by content:

```bash
hive search "auth middleware"
```

This uses FTS5 full-text search (or sqlite-vec semantic search if installed). See [Searching Your History](searching-your-history.md) for advanced query syntax.

## Ask Claude About Past Work

With the MCP server registered, Claude has access to your full history:

```
> What did I do with the payment service last week?
```

```
> Which sessions had the most corrections? I want to review those.
```

```
> How many tokens have I used this month?
```

See [Asking Claude](asking-claude.md) for more prompt ideas and MCP setup details.

## Tag Important Sessions

Mark sessions you want to find later:

```bash
hive tag a1b2c3d4 important
hive tag b2c3d4e5 needs-review
```

Tags show up in `hive log` output and are searchable.

## Track File History

See every session that touched a file:

```bash
hive lineage src/auth.py
```

```
Date        Summary                                    Commit   Author  Relationship
2026-04-19  Fix auth middleware token refresh           e5f6a1b2         modified
2026-04-15  Add JWT validation to auth middleware       c3d4e5f6         modified
2026-04-10  Initial auth module setup                   a1b2c3d4         created
```

This is useful for understanding how a file evolved across multiple AI-assisted sessions.

## Browse Projects

If you work across multiple projects, list them:

```bash
hive projects
```

```
Project                              Sessions  Messages  Last Active
~/projects/my-app                    87        2,341     2026-04-20
~/projects/api-gateway               32        892       2026-04-18
~/projects/shared-lib                23        614       2026-04-15
```

## End of Day: Everything Is Already Saved

There is no "commit" or "sync" step. Every session is stored in your local SQLite database at `~/.local/share/hive/store.db` the moment it happens. Your history is always up to date.

!!! tip "Backups"
    The database is a single SQLite file. Back it up with a simple copy:
    ```bash
    cp ~/.local/share/hive/store.db ~/.local/share/hive/store.db.bak
    ```
