# File Lineage

Trace any file's history through AI coding sessions and git commits. Lineage answers: "Who worked on this file, when, and what did they change?"

## Quick Start

```bash
hive lineage src/auth.py
```

This prints every session and commit linked to `src/auth.py`, newest first.

## How Edges Get Created

Hive builds lineage automatically through two hooks:

### PostToolUse Hook (session -> file)

When Claude Code uses a tool that touches a file (Read, Write, Edit), the `post-tool-use` hook fires. Hive creates an edge:

```
session --[touched]--> file
```

Every file read, written, or edited during a session gets linked. This happens in real time as you work.

### Git Post-Commit Hook (session -> commit -> files)

When you make a git commit, the post-commit hook fires and creates two types of edges:

```
session --[produced]--> commit
session --[committed]--> file   (for each file in the commit)
```

!!! info "Link Window"
    Hive links a commit to the **most recent active session** within a configurable time window. The default is 30 minutes. If no session was active in that window, the commit is recorded but not linked to a session.

    Configure this in your `.hive/config.toml`:

    ```toml
    [hooks]
    link_window_minutes = 30
    ```

## CLI Usage

Pass any file path -- hive resolves it to an absolute path automatically:

```bash
# Relative path works
hive lineage src/auth.py

# Absolute path works too
hive lineage /home/alice/code/api/src/auth.py
```

### Example Output

```
File: /home/alice/code/api/src/auth.py

Sessions (3):
  abc123def456  2025-04-18 14:32  "Fix JWT token expiration handling"
  789def012345  2025-04-15 09:11  "Add role-based access control"
  456abc789012  2025-04-10 16:45  "Initial auth module setup"

Commits (2):
  a1b2c3d  2025-04-18  Fix token expiration check (linked to abc123def456)
  d4e5f6g  2025-04-15  Add RBAC middleware (linked to 789def012345)
```

Each session entry shows its ID (prefix), timestamp, and summary. Commits show the hash, date, message, and which session produced them.

## MCP Lineage Tool

Claude Code can query lineage directly through the MCP server:

```json
{
  "tool": "lineage",
  "arguments": {
    "file_path": "src/auth.py"
  }
}
```

The response includes the same session and commit data, structured as JSON for programmatic use.

## REST API

Query lineage over HTTP:

```bash
curl http://localhost:3000/api/lineage/src/auth.py
```

## Interpreting Results

Lineage is most useful for:

- **Code review**: See which AI sessions touched a file before reviewing changes.
- **Debugging**: Find the session that introduced a bug by tracing the file's history.
- **Onboarding**: Understand how a module evolved by reading the linked session summaries.

!!! tip "Combine with `hive show`"
    Found an interesting session in the lineage? Drill into it:

    ```bash
    hive lineage src/auth.py
    # spot session abc123def456
    hive show abc123def456 --expand-tools
    ```

## Configuration

The key setting for lineage is the link window -- how far back hive looks for an active session when a commit is made.

```toml
# .hive/config.toml
[hooks]
link_window_minutes = 30  # default
```

A shorter window (e.g., 10 minutes) produces tighter links but may miss commits made after a break. A longer window (e.g., 60 minutes) catches more but may link commits to the wrong session.
