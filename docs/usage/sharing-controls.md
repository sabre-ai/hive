# Sharing Controls

Sharing is a per-project toggle that controls whether sessions are pushed to the team server. Nothing leaves your machine unless you explicitly enable it.

## Toggle sharing

```bash
# Enable sharing for the current project
hive config sharing on

# Disable sharing
hive config sharing off
```

These commands write to `<project>/.hive/config.toml`:

```toml title=".hive/config.toml"
sharing = "on"
```

### Targeting a different project

Use the `--project` flag to set sharing for a project you are not currently in:

```bash
hive config sharing on --project /path/to/other-project
```

## How auto-push works

When sharing is enabled, the push sequence runs automatically on every session capture:

```
Session Stop hook fires
        │
        ▼
  Capture + Enrich (local)
        │
        ▼
  Store in local store.db
        │
        ▼
  Is sharing = "on" for this project?
        │
   no ──┤── yes
        │     │
        ▼     ▼
      done   Export session as JSON
              │
              ▼
           Scrub secrets (client-side)
              │
              ▼
           POST to server_url/api/sessions
           (daemon thread, non-blocking)
              │
              ▼
            done
```

Key points:

- **Daemon thread** -- the POST runs in a background thread so the Claude Code hook returns immediately. Session capture never adds latency to your workflow.
- **Client-side scrubbing** -- secrets are removed before the payload leaves your machine. See [secret scrubbing](secret-scrubbing.md) for details.
- **Idempotent** -- the server uses the session ID as a unique key. Pushing the same session twice is a no-op.

## Check current state

Read the project config directly:

```bash
cat .hive/config.toml
```

```toml
sharing = "on"
```

Or verify from the server side that sessions are arriving:

```bash
curl -s http://team-server:3000/api/sessions?project=my-project | jq '.[0].id'
```

## Manual push

If you enabled sharing after some sessions were already captured, push historical sessions manually:

```bash
# Push all local sessions from the last 7 days
hive push --since 7d

# Dry run to see what would be pushed
hive push --since 7d --dry-run

# Push sessions for a specific project
hive push --project /path/to/project
```

!!! info "Push is additive"
    `hive push` only sends sessions that the server does not already have. It will not duplicate or overwrite existing sessions.

## Per-project isolation

Each project has its own `.hive/config.toml`. This means:

- Open-source projects can have `sharing = "off"` while internal projects share freely.
- Sensitive prototypes stay local until you are ready to share.
- The decision is stored in the project directory, visible in version control if you choose to commit it.

!!! tip "Add `.hive/` to `.gitignore`"
    The `.hive/` directory contains local config only. Add it to `.gitignore` so each developer controls their own sharing preference:
    ```bash
    echo ".hive/" >> .gitignore
    ```

## Global config vs. project config

| Setting | File | Scope |
|---|---|---|
| `server_url` | `~/.config/hive/config.toml` | All projects (global) |
| `sharing` | `<project>/.hive/config.toml` | Single project |

The global `server_url` tells hive where to push. The project-level `sharing` flag tells hive whether to push. Both must be set for auto-push to work.
