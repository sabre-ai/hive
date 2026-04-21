# Team Mode

Team mode connects your local hive client to a shared server so every AI coding session from every teammate is searchable in one place.

## Quick start

```bash
# On the server machine
hive serve --port 3000

# On each developer's laptop
hive config server_url http://team-server:3000
cd my-project && hive init
hive config sharing on
```

From this point, every Claude Code session in `my-project` is automatically pushed to the team server after the session ends.

## What team mode gives you

| Feature | Solo mode | Team mode |
|---|---|---|
| Local session capture | Yes | Yes |
| Full-text search | Local DB only | Local + server |
| MCP reads from | Local `store.db` | Team `server.db` |
| Secret scrubbing | N/A (no push) | Client-side before push |
| Shared history | No | Yes |

## How it works

```
Developer laptop                    Team server
┌─────────────────┐                ┌──────────────┐
│ Claude Code hook │──capture──►   │              │
│ hive store.db    │──auto-push──► │  server.db   │
│ scrub secrets    │               │  REST API    │
└─────────────────┘                │  MCP server  │
                                   └──────────────┘
```

1. **Capture** -- Claude Code hooks fire on session Stop, sending JSON to `hive`.
2. **Enrich** -- git context, file paths, and quality metrics are attached locally.
3. **Store** -- the session lands in the local `store.db`.
4. **Push** -- if `sharing = "on"` for the project, the session is scrubbed of secrets and POSTed to the team server in a background daemon thread (so the hook returns instantly).
5. **Serve** -- the team server exposes the same REST API and MCP tools, now backed by the collective `server.db`.

## Key configuration

Two config files control team mode:

```toml title="~/.config/hive/config.toml"
server_url = "http://team-server:3000"   # (1)!
```

1. Point this at your team server. Defaults to `http://localhost:3000` (solo mode).

```toml title="<project>/.hive/config.toml"
sharing = "on"   # (1)!
```

1. Per-project toggle. Only projects with sharing enabled push sessions.

!!! tip "Solo mode is the default"
    If `server_url` points to `localhost`, hive runs in solo mode -- MCP reads directly from the local `store.db` and nothing is pushed anywhere. No server process needed.

## Subpages

- [Server setup](server-setup.md) -- install and run the team server
- [Onboarding teammates](onboarding-teammates.md) -- steps each developer runs
- [Sharing controls](sharing-controls.md) -- per-project on/off and how auto-push works
- [Secret scrubbing](secret-scrubbing.md) -- what gets redacted and how to customize it
