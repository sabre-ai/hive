# Sharing Controls

Sharing is a per-project toggle that controls whether sessions are pushed to the team server. Nothing leaves your machine unless you explicitly enable it.

## Toggle sharing

```bash
# Enable sharing for the current project (one command does everything)
hive config sharing on --team-server http://team-server:3000 --project-name acme/my-app

# Disable sharing
hive config sharing off
```

This writes to both global and project config:

```toml title=".hive/config.toml (per-project)"
sharing = "on"
project = "acme/my-app"
```

The `--team-server` URL is saved to your global config (`~/.config/hive/config.toml`). The `--project-name` and `sharing` toggle are saved to the per-project config (`<project>/.hive/config.toml`).

### Project name

The project name is the canonical identity that ties sessions across team members. Everyone on the team must use the same name. If you're in a git repo, hive suggests the normalized remote URL as the default (e.g., `github.com/acme/my-app`).

For non-git projects (sales, docs), just pick a team-agreed name like `"sales-dashboard"`.

### Targeting a different project

Use the `--project` flag to set sharing for a project you are not currently in:

```bash
hive config sharing on --project /path/to/other-project --team-server http://team-server:3000 --project-name acme/other
```

### Teammates joining later

Commit `.hive/config.toml` to your repo so teammates get the project name automatically. They only need to set their server URL:

```bash
hive config sharing on --team-server http://team-server:3000
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
  Store in local store.db (with project_id from config)
        │
        ▼
  Is sharing = "on" for this project?
        │
   no ──┤── yes
        │     │
        ▼     ▼
      done   Export session as JSON (includes project_id)
              │
              ▼
           Scrub secrets (client-side)
              │
              ▼
           POST to server_url/api/sessions
           (daemon thread, non-blocking)
              │
              ▼
           Server auto-registers project if new
              │
              ▼
            done
```

Key points:

- **Daemon thread** -- the POST runs in a background thread so the Claude Code hook returns immediately. Session capture never adds latency to your workflow.
- **Client-side scrubbing** -- secrets are removed before the payload leaves your machine. See [secret scrubbing](secret-scrubbing.md) for details.
- **Idempotent** -- the server uses the session ID as a unique key. Pushing the same session twice is a no-op.
- **Project auto-registration** -- the team server creates a project entry automatically when it receives the first session for a new project name.

## Check current state

Read the project config directly:

```bash
cat .hive/config.toml
```

```toml
sharing = "on"
project = "acme/my-app"
```

Or verify from the server side that sessions are arriving:

```bash
curl -s http://team-server:3000/api/sessions?project=acme/my-app | jq '.[0].id'
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

!!! tip "Commit `.hive/config.toml` to your repo"
    Commit the `.hive/config.toml` file so teammates get the project name automatically when they clone the repo.

## Global config vs. project config

| Setting | File | Scope |
|---|---|---|
| `server_url` | `~/.config/hive/config.toml` | All projects (global) |
| `sharing` | `<project>/.hive/config.toml` | Single project |
| `project` | `<project>/.hive/config.toml` | Single project (required when sharing = on) |

The global `server_url` tells hive where to push. The project-level `sharing` flag tells hive whether to push. The `project` name tells the server which project the session belongs to. All three must be set for auto-push to work correctly on a team.
