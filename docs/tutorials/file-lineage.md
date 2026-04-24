# File & Commit Lineage

Trace any file or commit through AI coding sessions. Lineage answers: "Who worked on this file?" and "Which sessions produced this commit?"

## Quick Start

```bash
hive lineage --file src/auth.py      # sessions that touched a file
hive lineage --commit abc123f        # sessions that produced a commit
```

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

## File Lineage

Pass any file path — hive resolves it to an absolute path automatically:

```bash
hive lineage --file src/auth.py
hive lineage --file /home/alice/code/api/src/auth.py
```

Shows every session that read, wrote, or committed the file, along with associated commit SHAs.

## Commit Lineage

Find which AI sessions produced a given commit:

```bash
hive lineage --commit abc123f
```

Prefix matching is supported — you don't need the full SHA.

This is useful for:

- **PR context**: Before reviewing a PR, find the AI sessions behind each commit
- **Debugging**: Trace a bug back to the session that introduced it
- **Auditing**: Understand the AI conversation that led to a code change

Or ask Claude directly:

```
> Find sessions for commit abc123f
> What was the context behind the changes in commit abc123f?
```

Claude calls the `lineage` MCP tool with the commit SHA and returns the linked sessions.

## MCP Lineage Tool

Claude Code and Claude Desktop can query lineage directly:

```
> Which sessions touched src/auth.py?
> Find sessions for commit abc123f
```

The `lineage` tool accepts `file_path`, `session_id`, or `commit_sha`.

## Interpreting Results

Lineage is most useful for:

- **Code review**: See which AI sessions touched a file before reviewing changes
- **Debugging**: Find the session that introduced a bug by tracing the file or commit
- **Onboarding**: Understand how a module evolved by reading the linked session summaries

!!! tip "Combine with `hive show`"
    Found an interesting session in the lineage? Drill into it:

    ```bash
    hive lineage --file src/auth.py
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
