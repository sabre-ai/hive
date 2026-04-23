# Server Setup

Start a team server in one command, then point your teammates at it.

## Quick start (Docker — recommended)

The fastest way to get a production-ready team server with PostgreSQL and semantic search:

```bash
git clone https://github.com/sabre-ai/hive.git && cd hive
docker compose up -d
```

This starts two containers:

- **postgres** — PostgreSQL 16 with the pgvector extension
- **hive** — the team server, pre-configured to use PostgreSQL and pgvector search

Verify it's running:

```bash
curl -s http://localhost:3000/ | jq
```

```json
{"status": "ok", "version": "0.1.0"}
```

To stop: `docker compose down` (data persists in a Docker volume). To reset: `docker compose down -v`.

## Quick start (SQLite)

For small teams or quick local testing without Docker:

```bash
git clone https://github.com/sabre-ai/hive.git && cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
hive serve --port 3000
```

The server binds to `0.0.0.0:3000` and creates its database at `~/.local/share/hive/server.db`. Open `http://your-host:3000/` to verify:

```bash
curl -s http://localhost:3000/ | jq
```

```json
{"status": "ok", "version": "0.1.0"}
```

!!! warning "No authentication in MVP"
    The current server has no built-in auth. Run it on a trusted network or place it behind an authenticating reverse proxy (OAuth2 Proxy, Tailscale, etc.).

## Server flags

| Flag | Default | Description |
|---|---|---|
| `--port` | `3000` | Port to listen on |
| `--no-search` | off | Disable the semantic search backend |

Use `--no-search` if you do not need vector search or want to avoid loading the embedding model on the server.

## Running behind nginx

Place hive behind nginx for TLS termination and access control:

```nginx title="/etc/nginx/sites-enabled/hive"
server {
    listen 443 ssl;
    server_name hive.internal;

    ssl_certificate     /etc/ssl/certs/hive.pem;
    ssl_certificate_key /etc/ssl/private/hive.key;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With this in place, teammates set `server_url = "https://hive.internal"` in their config.

## systemd unit for production

Create `/etc/systemd/system/hive.service`:

```ini title="hive.service"
[Unit]
Description=hive team server
After=network.target

[Service]
Type=simple
User=hive
ExecStart=/usr/local/bin/hive serve --port 3000
Restart=on-failure
Environment=HOME=/home/hive

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hive
sudo journalctl -u hive -f   # watch logs
```

## PostgreSQL setup (without Docker)

If you prefer to run PostgreSQL natively instead of Docker:

1. Install PostgreSQL 16+ with the [pgvector extension](https://github.com/pgvector/pgvector).

2. Create the database:
    ```bash
    createdb hive
    psql hive -c "CREATE EXTENSION IF NOT EXISTS vector"
    ```

3. Install hive with PostgreSQL dependencies:
    ```bash
    pip install -e ".[postgres]"
    ```

4. Configure hive (`~/.config/hive/config.toml`):
    ```toml
    db_url = "postgresql://user:pass@localhost:5432/hive"

    [search]
    backend = "pgvector"
    ```

5. Start the server:
    ```bash
    hive serve --port 3000
    ```

Migrations run automatically on startup.

### Migrating from SQLite to PostgreSQL

If you have an existing SQLite-based team server:

1. Start the new PostgreSQL-backed server
2. Re-push sessions from each developer's machine:
    ```bash
    hive push   # pushes all local sessions to the new server
    ```

## Database location

### SQLite (default)

The server stores everything in a single SQLite file:

```
~/.local/share/hive/server.db
```

This path follows `$XDG_DATA_HOME`. Override it by setting `XDG_DATA_HOME` in the systemd unit's `Environment=` line. For example:

```ini
Environment=HOME=/home/hive
Environment=XDG_DATA_HOME=/data/hive
```

This puts the database at `/data/hive/hive/server.db`.

### PostgreSQL

When `db_url` is set to a PostgreSQL URL, hive ignores `server_db_path` and connects directly to the database. Data persists in PostgreSQL's data directory (or in a Docker volume when using Docker Compose).

!!! note "Separate from client DB"
    Each developer's laptop has its own `store.db` for local sessions. The server database (SQLite or PostgreSQL) is the shared, team-wide store. They use the same schema but are independent.

## File permissions

Lock down the data directory:

```bash
sudo mkdir -p /home/hive/.local/share/hive
sudo chown -R hive:hive /home/hive/.local/share/hive
sudo chmod 700 /home/hive/.local/share/hive
```

## Interactive API docs

The server includes auto-generated API documentation at `/api/docs` (Swagger UI) and `/api/openapi.json` (OpenAPI spec). Use these to explore endpoints or test queries interactively.
