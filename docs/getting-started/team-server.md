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

!!! warning "No built-in auth in MVP"
    Run on a trusted network or behind an authenticating reverse proxy (OAuth2 Proxy, Tailscale, etc.).

## Connect each developer's machine

Set the server URL in `~/.config/hive/config.toml`:

```toml
server_url = "http://team-server:3000"
```

Enable sharing:

```bash
hive config sharing on
```

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
