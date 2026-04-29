# REST API Reference

All endpoints served by `hive serve`. Base URL: `http://localhost:3000` (or your configured port).

!!! tip
    Interactive Swagger docs are available at `/api/docs` when the server is running.

---

## `GET /`

Health check.

**Response:**

```json
{"status": "ok", "version": "0.1.0"}
```

```bash
curl http://localhost:3000/
```

---

## `GET /api/sessions`

List sessions with filtering and pagination.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | -- | Filter by source (e.g. `claude_code`) |
| `project` | string | -- | Filter by project path |
| `author` | string | -- | Filter by author |
| `since` | string | -- | ISO date, sessions after this time |
| `until` | string | -- | ISO date, sessions before this time |
| `tag` | string | -- | Filter by tag annotation |
| `limit` | int | `50` | Results per page (1--500) |
| `offset` | int | `0` | Pagination offset (>=0) |
| `sort_by` | string | -- | Sort field |
| `min_tokens` | int | -- | Minimum token count |
| `model` | string | -- | Filter by model |
| `min_correction_rate` | float | -- | Minimum correction rate |

```bash
# List recent sessions
curl "http://localhost:3000/api/sessions?limit=10"

# Filter by project and author
curl "http://localhost:3000/api/sessions?project=/code/api&author=alice&since=2025-04-01"

# Filter by tag
curl "http://localhost:3000/api/sessions?tag=important"
```

**Response:** Array of session objects.

---

## `POST /api/sessions`

Import a session. Returns `201 Created`.

**Body** (`SessionPushPayload`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Session ID |
| `source` | string | Yes | Source adapter name |
| `project_path` | string | No | Absolute project path (local to the pushing machine) |
| `project_id` | string | No | Canonical project name for cross-machine grouping (e.g., `acme/my-app`). Auto-registers the project on first push. |
| `author` | string | No | Author name |
| `started_at` | string | No | ISO timestamp |
| `ended_at` | string | No | ISO timestamp |
| `message_count` | int | No | Default `0` |
| `summary` | string | No | Session summary |
| `messages` | array | No | Message objects |
| `enrichments` | array | No | Enrichment objects |
| `annotations` | array | No | Annotation objects |
| `edges` | array | No | Edge objects |

```bash
curl -X POST http://localhost:3000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "sess_abc123",
    "source": "claude_code",
    "project_path": "/home/alice/code/api",
    "project_id": "acme/my-app",
    "author": "alice",
    "messages": [
      {"role": "human", "content": "Fix the login bug"},
      {"role": "assistant", "content": "I will look at the auth module..."}
    ]
  }'
```

**Response:**

```json
{"status": "ok", "session_id": "sess_abc123"}
```

---

## `GET /api/sessions/{session_id}`

Get a single session with messages and metadata.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `detail` | string | -- | Detail level |
| `role` | string | -- | Filter messages by role |
| `msg_limit` | int | -- | Limit number of messages |
| `msg_offset` | int | `0` | Offset into messages |

```bash
# Get full session
curl http://localhost:3000/api/sessions/sess_abc123

# Get only assistant messages, first 10
curl "http://localhost:3000/api/sessions/sess_abc123?role=assistant&msg_limit=10"
```

**Response:** Session object with nested messages, enrichments, annotations, and edges. Returns `404` if not found.

---

## `DELETE /api/sessions/{session_id}`

Delete a session and all related data.

```bash
curl -X DELETE http://localhost:3000/api/sessions/sess_abc123
```

**Response:** `200 OK` on success, `404` if not found.

---

## `GET /api/search`

Full-text search across sessions.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | **required** | Search query (min 1 char) |
| `project` | string | -- | Filter by project |
| `author` | string | -- | Filter by author |
| `since` | string | -- | ISO date |
| `until` | string | -- | ISO date |
| `limit` | int | `20` | Results (1--200) |

```bash
# Search for sessions mentioning database migrations
curl "http://localhost:3000/api/search?q=database+migration"

# Scoped search
curl "http://localhost:3000/api/search?q=auth&project=/code/api&limit=5"
```

**Response:** Array of matching sessions with relevance ranking.

---

## `GET /api/lineage/{path:path}`

Get the lineage of a file -- all sessions and commits that touched it.

```bash
curl http://localhost:3000/api/lineage/src/auth.py
```

**Response:** Object with sessions and commits linked to the file.

---

## `GET /api/stats`

Aggregate statistics.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `project` | string | -- | Filter by project |
| `since` | string | -- | ISO date |
| `group_by` | string | -- | One of: `project`, `model`, `author`, `week` |

```bash
# Overall stats
curl http://localhost:3000/api/stats

# Stats grouped by author since January
curl "http://localhost:3000/api/stats?group_by=author&since=2025-01-01"
```

---

## `GET /api/projects`

List all projects with session counts.

```bash
curl http://localhost:3000/api/projects
```

**Response:** Array of project objects.

---

## `POST /api/annotations`

Create an annotation on a session. Returns `201 Created`.

**Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Target session |
| `type` | string | Yes | One of: `tag`, `comment`, `rating` |
| `value` | string | Yes | Annotation value |
| `author` | string | No | Who created it |

```bash
curl -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess_abc123", "type": "tag", "value": "important"}'
```

**Response:**

```json
{
  "id": 1,
  "session_id": "sess_abc123",
  "type": "tag",
  "value": "important",
  "author": null
}
```
