# Asking Claude About Your History

The hive MCP server gives Claude Code direct access to your session history. In solo mode, it reads from your local SQLite database -- no running server required. In team mode, it reads from the shared server.

## Setup

Register the MCP server with Claude Code:

```bash
claude mcp add --scope user --transport stdio hive -- hive mcp
```

Restart Claude Code and verify:

```
/mcp
```

You should see `hive` listed with 9 available tools.

!!! info "No server needed"
    In solo mode, the MCP server uses `LocalBackend` to read directly from `~/.local/share/hive/store.db`. The `Config.is_solo` property detects this by checking whether `server_url` points to `localhost`, `127.0.0.1`, or `::1`. You do **not** need to run `hive serve`.

## How It Works

When you ask Claude a question about your coding history, it calls the hive MCP tools to fetch relevant data. The flow is:

1. You ask a question in natural language
2. Claude selects the appropriate hive tool (search, recent, stats, etc.)
3. The MCP server queries your local SQLite database
4. Claude receives structured JSON results
5. Claude synthesizes an answer from the data

This all happens in a single conversation turn.

## Example Prompts

### Finding past work

```
> What sessions touched the auth middleware this week?
```

Claude calls `search` with your query and a `since` filter, then summarizes the matching sessions.

```
> Show me the conversation that led to the payment service refactor
```

Claude calls `search` to find the session, then `get_session` with `detail=messages` to retrieve the full conversation.

### Usage and productivity

```
> How many tokens did I use this week?
```

Claude calls `stats` with a `since` filter and reports the token breakdown.

```
> Which of my sessions had the most corrections?
```

Claude calls `recent` with `sort_by=corrections` to find sessions where you had to correct Claude the most.

### File history

```
> What sessions modified src/api/routes.py?
```

Claude calls `lineage` with the file path and returns every session that read or wrote that file, along with related commits.

### Cross-session analysis

```
> Compare the approaches I used for error handling in the last 5 sessions
```

Claude calls `recent` to get the sessions, then `get_session` for each to read the conversations, and synthesizes a comparison.

## The 9 MCP Tools

| Tool | Description | Key Parameters |
|---|---|---|
| `search` | Full-text search across sessions | `query`, `project`, `author`, `since` |
| `get_session` | Retrieve full session data | `session_id`, `detail`, `role`, `limit`, `offset` |
| `lineage` | File or session lineage graph | `file_path` or `session_id` |
| `recent` | List recent sessions | `project`, `author`, `n`, `sort_by`, `min_tokens`, `model`, `min_correction_rate` |
| `stats` | Aggregated statistics | `project`, `since`, `group_by` |
| `delete` | Delete a session | `session_id` |
| `capture_session` | Save a conversation to hive | `title`, `content`, `project`, `tags` |
| `link_sessions` | Link two sessions (design to implementation) | `source_session_id`, `target_session_id`, `relationship` |
| `current_session` | Get the most recent session ID | `project` |

### Filtering with `recent`

The `recent` tool supports advanced filtering that is useful for targeted queries:

```
> Show me my longest sessions from this month
```

Claude uses `recent` with `sort_by=messages` and a `since` filter.

```
> Which sessions used the most tokens?
```

Claude uses `recent` with `sort_by=tokens`.

```
> Find sessions with a high correction rate
```

Claude uses `recent` with `min_correction_rate=0.3` to surface sessions where you corrected Claude frequently.

### Grouping with `stats`

The `stats` tool supports `group_by` for breakdowns:

```
> Break down my token usage by project
```

Claude uses `stats` with `group_by=project`.

```
> Show me a weekly summary of my sessions
```

Claude uses `stats` with `group_by=week`.

## Tips

!!! tip "Be specific about time"
    Prompts with time references ("this week", "last month", "since April") help Claude add `since` filters to its queries, producing more relevant results.

!!! tip "Ask follow-up questions"
    After Claude finds a session, ask it to dig deeper: "Show me the full conversation from that session" or "What files were changed in that session?"
