# Your First Session

This walkthrough takes you from zero to a captured, searchable AI coding session in under five minutes.

## 1. Initialize Hive

Navigate to your project and run `hive init`:

```bash
cd ~/projects/my-app
hive init
```

Expected output:

```
Setting up hive...

  Creating database... ✓
  Created config.toml... ✓
  Installing Claude Code hooks... ✓
  Installing git post-commit hook... ✓
  Session sharing... Enable sharing to team server? [y/N]: n
  Backfilling existing sessions... ✓ (3 sessions)

  MCP server configuration:
    Run this command to register hive with Claude Code:
    claude mcp add --transport stdio hive -- hive mcp
    Then restart Claude Code and verify with /mcp

hive is ready!
  Database: ~/.local/share/hive/store.db
  Config:   ~/.config/hive/config.toml
```

!!! info "Backfilling"
    Hive scans for existing Claude Code session files and imports them. If you have been using Claude Code already, your past sessions appear immediately.

## 2. Have a Claude Code Session

Open Claude Code in your project and have a conversation. Anything works -- ask Claude to write a function, review code, fix a bug. The hooks capture everything automatically.

```bash
claude
```

```
> Can you add input validation to the signup handler?
```

Once the session ends (or you start a new one), hive captures it.

## 3. View Recent Sessions

```bash
hive log
```

```
a1b2c3d4e5f6  2026-04-20 14:32  claude-code (12 msgs)
  Add input validation to signup handler

f7e8d9c0b1a2  2026-04-20 10:15  claude-code (8 msgs)
  Fix database connection pooling

...
```

Use `-n` to control how many sessions to show:

```bash
hive log -n 5
```

## 4. Inspect a Session

Copy a session ID prefix from the log and pass it to `hive show`:

```bash
hive show a1b2c3d4
```

This displays the full session: summary, enrichments (git branch, files touched, quality metrics), and the conversation. Add `--expand-tools` to see tool use details:

```bash
hive show a1b2c3d4 --expand-tools
```

## 5. Search Your History

Full-text search across all captured sessions:

```bash
hive search "validation"
```

```
ID           Date        Author  Source       Summary                             Match
a1b2c3d4e5f6 2026-04-20         claude-code  Add input validation to signup...   ...input validation for email...
```

Filter by date range:

```bash
hive search "database" --since 2026-04-01 --until 2026-04-15
```

## 6. Register the MCP Server

The MCP server lets Claude Code search and reference your past sessions during conversations.

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

!!! tip "Scope"
    Use `--scope user` to make hive available across all your projects. Use `--scope project` to limit it to the current project.

Restart Claude Code and verify the connection:

```
/mcp
```

You should see `hive` listed with 6 tools available.

## 7. Ask Claude About Your History

Now Claude can access your session history. Try prompts like:

```
> What did I work on today?
```

```
> Show me the session where I added input validation
```

```
> Which files have I changed the most this week?
```

Claude uses the hive MCP tools (search, recent, lineage, stats) to pull relevant sessions and answer with context from your actual coding history.

## Next Steps

- [Solo Mode Workflow](../solo-mode/workflow.md) -- day-to-day patterns for individual use
- [Searching Your History](../solo-mode/searching-your-history.md) -- advanced search techniques
- [Asking Claude](../solo-mode/asking-claude.md) -- getting the most out of MCP integration
