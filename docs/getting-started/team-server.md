# Team Server

Share sessions across your team so everyone's Claude can search the collective history.

## Option A: Docker (recommended)

The easiest way to run a production team server — one command starts PostgreSQL (with pgvector) and the hive server together:

```bash
git clone https://github.com/sabre-ai/hive.git && cd hive
docker compose up -d
```

The server is now running at `http://localhost:3000` backed by PostgreSQL with semantic search via pgvector.

## Option B: SQLite (simple)

For quick local testing or small teams, install from source and run:

```bash
hive serve --port 3000
```

!!! tip "Secure your server"
    Enable [built-in OIDC authentication](../tutorials/authentication.md) to protect write endpoints, or run behind an authenticating reverse proxy.

## Connect each developer's machine

One command transitions a project from solo to team mode:

```bash
cd your-project
hive config sharing on --team-server http://team-server:3000 --project-name acme/my-app
```

This writes the server URL to your global config and the project name to the per-project config (`.hive/config.toml`). The project name is the canonical identity that ties sessions across team members — everyone on the team must use the same name.

!!! tip "Commit `.hive/config.toml` to your repo"
    Teammates who clone the repo will already have the project name. They only need to run:
    ```bash
    hive config sharing on --team-server http://team-server:3000
    ```

!!! tip "Git repos get a suggested default"
    If you're in a git repo and omit `--project-name`, hive will suggest the normalized remote URL (e.g., `github.com/acme/my-app`) as the default.

!!! note "First time installing hive?"
    If you haven't completed the [Quick Start](solo-mode.md), install hive first:
    ```bash
    curl https://sabre-ai.github.io/hive/install.sh | bash
    cd your-project
    hive init                                                  # say Y to sharing
    ```

Verify the connection:

```bash
curl -s http://team-server:3000/ | jq .status              # should print "ok"
hive log                                                    # see team sessions
```

Sessions auto-push to the server in the background. Secrets are scrubbed client-side before leaving the laptop.

## Backfill existing sessions

If you already have local sessions from before connecting to the server, push them in one go:

```bash
hive push                          # push all local sessions
hive push --project your-project   # push only one project
hive push --dry-run                # preview what would be pushed
```

You now have shared, searchable AI coding history for your team.

## Next Steps

- [Sharing Controls](../tutorials/sharing-controls.md) — per-project sharing settings
- [Security & Privacy](../security.md) — how secrets are scrubbed
- [Configuration](../reference/configuration.md) — full config reference
