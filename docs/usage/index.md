# Usage

Hive supports two modes of operation: **solo** (local only) and **team** (shared server). Both modes capture sessions automatically -- the difference is whether sessions stay on your machine or are shared with teammates.

## Solo vs Team Mode

| Feature | Solo mode | Team mode |
|---|---|---|
| Local session capture | Yes | Yes |
| Full-text search | Local DB only | Local + server |
| MCP reads from | Local `store.db` | Team `server.db` |
| Secret scrubbing | N/A (no push) | Client-side before push |
| Shared history | No | Yes |
| Requires `hive serve` | No | Yes (on server) |

## Solo Mode

Solo mode is the default. Everything stays on your local machine -- no server, no network, no shared infrastructure. Your SQLite database at `~/.local/share/hive/store.db` is the single source of truth.

**Setup:**

```bash
cd your-project
hive init
```

That's it. Sessions are captured automatically via Claude Code hooks. The MCP server reads directly from your local database using `LocalBackend` -- no `hive serve` needed.

!!! note
    Solo mode is active when `server_url` points to `localhost` (the default). Hive detects this by checking whether `server_url` resolves to `localhost`, `127.0.0.1`, or `::1`.

### Key capabilities

- **Automatic capture** -- every Claude Code session is captured via hooks (session start, tool use, compaction, stop)
- **Local search** -- FTS5 keyword search out of the box; install `pip install "hive-team[search]"` for semantic search via sqlite-vec
- **MCP integration** -- register the MCP server and Claude can search your full history
- **File lineage** -- track how files evolved across AI-assisted sessions with `hive lineage`

## Team Mode

Team mode connects your local hive client to a shared server so every AI coding session from every teammate is searchable in one place.

**Setup:**

```bash
# On the server machine
hive serve --port 3000

# On each developer's laptop
hive init
hive config sharing on
```

Set the server URL in `~/.config/hive/config.toml`:

```toml
server_url = "http://team-server:3000"
```

### How it works

```
Developer laptop                    Team server
+-----------------+                +--------------+
| Claude Code hook |--capture-->   |              |
| hive store.db    |--auto-push--> |  server.db   |
| scrub secrets    |               |  REST API    |
+-----------------+                |  MCP server  |
                                   +--------------+
```

1. **Capture** -- Claude Code hooks fire on session Stop, sending JSON to `hive`.
2. **Enrich** -- git context, file paths, and quality metrics are attached locally.
3. **Store** -- the session lands in the local `store.db`.
4. **Push** -- if `sharing = "on"` for the project, the session is scrubbed of secrets and POSTed to the team server in a background daemon thread (so the hook returns instantly).
5. **Serve** -- the team server exposes the same REST API and MCP tools, now backed by the collective `server.db`.

### Key configuration

Two config files control team mode:

```toml title="~/.config/hive/config.toml"
server_url = "http://team-server:3000"
```

```toml title="<project>/.hive/config.toml"
sharing = "on"
```

## Subpages

- [Daily Workflow](workflow.md) -- day-to-day patterns for using hive
- [Searching Your History](searching-your-history.md) -- CLI search, FTS5 syntax, search backends
- [Asking Claude About Your Work](asking-claude.md) -- MCP setup and prompt examples
- [Setting Up the Team Server](server-setup.md) -- install and run the team server
- [Onboarding Teammates](onboarding-teammates.md) -- steps each developer runs
- [Sharing Controls](sharing-controls.md) -- per-project on/off and how auto-push works
- [Secret Scrubbing](secret-scrubbing.md) -- what gets redacted and how to customize it
