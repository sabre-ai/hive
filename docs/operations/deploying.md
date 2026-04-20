# Deploying

Three options for running the hive team server in production: systemd, nginx reverse proxy, and Docker Compose.

## Option 1: systemd

Create a dedicated user and systemd unit:

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin hive
sudo -u hive pip install hive-team
```

```ini title="/etc/systemd/system/hive.service"
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

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hive
```

Verify:

```bash
curl -s http://localhost:3000/ | jq .status
```

```
"ok"
```

## Option 2: nginx reverse proxy

Place hive behind nginx for TLS, rate limiting, or authentication:

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

!!! warning "Add authentication"
    Hive has no built-in auth. Use nginx basic auth, OAuth2 Proxy, or a VPN to restrict access. Do not expose the server to the public internet without an auth layer.

## Option 3: Docker Compose

```yaml title="docker-compose.yml"
version: "3.8"
services:
  hive:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - hive-data:/data
    environment:
      - XDG_DATA_HOME=/data
    command: hive serve --port 3000
volumes:
  hive-data:
```

```bash
docker compose up -d
docker compose logs -f hive
```

The database lands at `/data/hive/server.db` inside the container, persisted in the `hive-data` volume.

## Database location

The server writes to a single SQLite file:

| Deployment | Database path |
|---|---|
| systemd (default) | `/home/hive/.local/share/hive/server.db` |
| systemd (custom `XDG_DATA_HOME`) | `$XDG_DATA_HOME/hive/server.db` |
| Docker Compose | `/data/hive/server.db` (inside container) |

## File permissions

Lock down the data directory to prevent unauthorized access:

```bash
sudo chmod 700 /home/hive/.local/share/hive
sudo chown -R hive:hive /home/hive/.local/share/hive
```

!!! tip "SQLite WAL mode"
    Hive uses SQLite in WAL (Write-Ahead Logging) mode for concurrent read performance. You will see `server.db-wal` and `server.db-shm` files alongside the main database. These are normal -- do not delete them while the server is running.

## Backup considerations

The `server.db` file is the single source of truth for team history. Set up regular backups:

```bash
# Safe hot backup using SQLite's .backup command
sqlite3 /home/hive/.local/share/hive/server.db \
    ".backup /backups/server-$(date +%Y%m%d).db"
```

See [Backup and Restore](backup-restore.md) for a full backup strategy including cron scheduling and restore procedures.

## Health check

Add a health check to your monitoring:

```bash
curl -sf http://localhost:3000/ | jq -e '.status == "ok"'
```

This returns exit code 0 when the server is healthy, making it suitable for systemd watchdog scripts, Docker health checks, or uptime monitors.

## Disabling semantic search

If the server machine lacks resources for the embedding model, start without search:

```bash
hive serve --port 3000 --no-search
```

Full-text search (FTS5) still works. Only vector-based semantic search is disabled.
