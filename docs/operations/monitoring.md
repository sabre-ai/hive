# Monitoring

Keep tabs on your hive team server with health checks, log monitoring, and session statistics.

## Health endpoint

The server exposes a health check at the root path:

```bash
curl -s http://localhost:3000/ | jq
```

```json
{"status": "ok", "version": "0.1.0"}
```

Use this in monitoring scripts or uptime checks:

```bash
# Exit code 0 if healthy, non-zero otherwise
curl -sf http://localhost:3000/ | jq -e '.status == "ok"' > /dev/null
```

### Docker health check

```yaml title="docker-compose.yml"
services:
  hive:
    # ...
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:3000/"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### systemd watchdog

Use a simple timer to check health and restart on failure:

```bash title="/usr/local/bin/hive-healthcheck.sh"
#!/bin/bash
if ! curl -sf http://localhost:3000/ > /dev/null 2>&1; then
    echo "$(date): hive health check failed, restarting" >> /var/log/hive-health.log
    systemctl restart hive
fi
```

```bash title="crontab -e"
* * * * * /usr/local/bin/hive-healthcheck.sh
```

## Logs

Hive logs to stderr by default. With systemd, logs go to the journal:

```bash
# Follow live logs
sudo journalctl -u hive -f

# Last 100 lines
sudo journalctl -u hive -n 100

# Logs since today
sudo journalctl -u hive --since today
```

### Log levels

By default, hive logs at INFO level. Key events to watch for:

| Log message | Meaning |
|---|---|
| Session imported | A client pushed a session successfully |
| Search backend unavailable | Semantic search is down, FTS5 still works |
| Push failed | Client could not reach the server (check client-side logs) |

!!! tip "Debug logging"
    For more detail when troubleshooting, set the `HIVE_LOG_LEVEL` environment variable:
    ```bash
    HIVE_LOG_LEVEL=DEBUG hive serve --port 3000
    ```

## Session statistics

Use `hive stats` to get a quick overview of session counts and trends:

```bash
# Overall stats
hive stats

# Stats for a specific project
hive stats --project my-project

# Stats since a date
hive stats --since 7d
```

Example output:

```
Sessions: 142
Projects: 5
Messages: 3,847
  Human: 1,923
  Assistant: 1,924
Top projects:
  my-app        68 sessions
  api-service   42 sessions
  docs          32 sessions
```

## Interactive API docs

The server includes Swagger UI for exploring and testing the API interactively:

```
http://localhost:3000/api/docs
```

The OpenAPI spec is available at:

```
http://localhost:3000/api/openapi.json
```

## Key endpoints to monitor

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Health check |
| `/api/sessions` | GET | List sessions (verify data is flowing) |
| `/api/stats` | GET | Session counts and metrics |
| `/api/search?q=term` | GET | Test search functionality |
| `/api/projects` | GET | List known projects |

## Alerting checklist

Set up alerts for these conditions:

- **Server down** -- health endpoint returns non-200 or times out
- **No new sessions** -- `GET /api/stats` shows no sessions in the last 24 hours (may indicate broken hooks or push failures)
- **Disk space** -- the SQLite database grows with usage; monitor the data directory
- **Search backend** -- if using semantic search, monitor for backend availability

```bash
# Quick disk usage check
du -h ~/.local/share/hive/server.db
```

!!! note "Push failures are client-side"
    If sessions are not arriving at the server, the issue is usually on the client. Check that sharing is enabled, the server URL is correct, and the network path is open. Push failures are logged on the client, not the server.
