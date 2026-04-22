# Searching Your History

Hive provides multiple ways to find past sessions: full-text search, filtered browsing, detailed inspection, and MCP-powered natural language queries.

## Full-Text Search

The primary search command:

```bash
hive search "database migration"
```

### Flags

| Flag | Description | Example |
|---|---|---|
| `--project` | Filter by project path | `--project my-app` |
| `--author` | Filter by author name | `--author alice` |
| `--since` | Sessions after this date | `--since 2026-04-01` |
| `--until` | Sessions before this date | `--until 2026-04-15` |

Combine flags freely:

```bash
hive search "auth" --project api-gateway --since 2026-04-01
```

### FTS5 Query Syntax

Hive uses SQLite FTS5 under the hood. You can use its full query syntax for precise searches:

```bash
# AND (implicit -- all terms must match)
hive search "database migration"

# Explicit AND
hive search "database AND migration"

# OR
hive search "postgres OR mysql"

# NOT
hive search "database NOT migration"

# Exact phrase
hive search '"connection pooling"'

# Prefix match
hive search "auth*"
```

!!! tip "Quoting"
    Wrap exact phrases in double quotes inside single quotes to prevent shell expansion: `'"exact phrase"'`.

## Browsing Recent Sessions

Use `hive log` to browse your session history chronologically:

```bash
# Last 20 sessions (default)
hive log

# Last 5 sessions
hive log -n 5

# Filter by project
hive log --project my-app
```

Output shows the session ID prefix, timestamp, source, message count, summary, and any tags:

```
a1b2c3d4e5f6  2026-04-20 14:32  claude-code (12 msgs)
  Add input validation to signup handler
  tags: important

f7e8d9c0b1a2  2026-04-20 10:15  claude-code (8 msgs)
  Fix database connection pooling
```

## Inspecting a Session

Once you find a session of interest, inspect it in detail:

```bash
hive show a1b2c3d4
```

!!! note "Prefix matching"
    You do not need the full session ID. Any unique prefix works. Hive resolves partial IDs automatically.

This displays:

- **Header**: summary, source, author, message count, timestamps
- **Enrichments**: git branch, commit, diff stats, files touched, quality metrics
- **Annotations**: tags, comments, ratings
- **Messages**: the full human/assistant conversation

### Expanding Tool Use

By default, tool use messages (file reads, writes, shell commands) are collapsed. Expand them with:

```bash
hive show a1b2c3d4 --expand-tools
```

This is useful for reviewing exactly what changes Claude made during a session.

## Searching via MCP

When Claude Code has the hive MCP server registered, you can search with natural language:

```
> Find sessions where I worked on the auth middleware
```

```
> What conversations involved database schema changes this month?
```

Claude uses the `search` MCP tool behind the scenes, which supports the same filtering as the CLI. The advantage is that Claude can interpret results, follow up with `get_session` to read full conversations, and synthesize answers across multiple sessions.

See [Asking Claude](asking-claude.md) for setup and prompt examples.

## Search Backends

Hive supports two search backends:

=== "sqlite-vec (default)"

    Semantic search using sentence embeddings stored in SQLite. Understands meaning, not just keywords.

    ```bash
    # Install the extras
    pip install "hive-team[search]"

    # Rebuild the index
    hive reindex
    ```

    Queries like `"how did I handle errors"` match sessions about error handling even if those exact words were not used.

=== "FTS5 (fallback)"

    Keyword-based full-text search built into SQLite. Always available, no extras needed.

    Works best with specific terms and the FTS5 query syntax described above.

If `sqlite-vec` is installed, hive uses it automatically. Otherwise it falls back to FTS5.
