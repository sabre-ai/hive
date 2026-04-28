# Asking Claude About Your History

The hive MCP server gives Claude Code direct access to session history — yours in solo mode, or your entire team's in team mode. Ask questions in natural language and Claude queries the data for you.

## Setup

Register the MCP server with Claude Code:

```bash
claude mcp add --scope user --transport stdio hive -- /path/to/hive/.venv/bin/hive mcp
```

Restart Claude Code and verify:

```
/mcp
```

You should see `hive` listed with 8 available tools.

!!! info "Solo and team mode"
    In **solo mode**, the MCP server reads directly from your local store — no running server needed. In **team mode**, it queries the shared server, giving Claude visibility across all team members' sessions.

## How It Works

When you ask Claude a question about your coding history, it calls the hive MCP tools to fetch relevant data. The flow is:

1. You ask a question in natural language
2. Claude selects the appropriate hive tool (search, recent, stats, etc.)
3. The MCP server queries your session store (local in solo mode, shared server in team mode)
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

!!! example "Team mode"
    ```
    > Has anyone on the team worked on the auth middleware before?
    ```

    Claude calls `search` without an `author` filter, returning matching sessions from any team member.

### File history

```
> What sessions modified src/api/routes.py?
```

Claude calls `lineage` with the file path and returns every session that read or wrote that file, along with related commits.

!!! example "Team mode"
    ```
    > Who last modified the payment service and what did they change?
    ```

    Claude calls `lineage` with the file path, sees sessions from multiple authors, then `get_session` on the most recent to show the full conversation.

### Cross-session analysis

```
> Compare the approaches I used for error handling in the last 5 sessions
```

Claude calls `recent` to get the sessions, then `get_session` for each to read the conversations, and synthesizes a comparison.

!!! example "Team mode"
    ```
    > What patterns has the team converged on for database migrations?
    ```

    Claude calls `search` for migration-related sessions across all authors and synthesizes common approaches.

## The MCP Tools

| Tool | Description | Key Parameters |
|---|---|---|
| `search` | Full-text search across sessions | `query`, `project`, `author`, `since` |
| `get_session` | Retrieve full session data | `session_id`, `detail`, `role`, `limit`, `offset` |
| `lineage` | File, session, or commit lineage | `file_path`, `session_id`, or `commit_sha` |
| `recent` | List recent sessions | `project`, `author`, `n`, `sort_by`, `min_correction_rate` |
| `stats` | Aggregated statistics | `project`, `since`, `group_by` |
| `delete` | Delete a session | `session_id` |
| `capture_session` | Save a conversation to hive | `title`, `content`, `project`, `tags` |
| `link_sessions` | Link two sessions | `source_session_id`, `target_session_id` |

## Tips

!!! tip "Be specific about time"
    Prompts with time references ("this week", "last month", "since April") help Claude add `since` filters to its queries, producing more relevant results.

!!! tip "Ask follow-up questions"
    After Claude finds a session, ask it to dig deeper: "Show me the full conversation from that session" or "What files were changed in that session?"

!!! tip "Team queries need no special syntax"
    In team mode, Claude automatically searches across all team members. To narrow to one person, just mention their name — Claude will add an `author` filter.
