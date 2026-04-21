# Store Layer

The store layer handles all persistence via SQLite. It provides a single `QueryAPI` class that every other component uses for reads and writes.

## Quick Example

```python
from hive.store.query import QueryAPI

api = QueryAPI()

# Search sessions
results = api.search_sessions("refactor auth module", project="my-app")

# Get full session with messages
session = api.get_session("abc-123", detail="messages")

# File lineage
lineage = api.get_lineage("/src/auth.py", id_type="file")
```

## SQLAlchemy + Alembic

The store layer uses **SQLAlchemy 2.0** for all database access and **Alembic** for schema migrations.

- ORM models are defined in `src/hive/store/models.py`
- Migrations live in `src/hive/store/alembic/`
- `init_db()` runs `alembic upgrade head` to apply migrations automatically
- Existing pre-migration databases are auto-detected and stamped without re-running DDL

Every SQLite connection is configured with:

- **WAL mode** (`PRAGMA journal_mode=WAL`) -- enables concurrent readers with a single writer
- **Foreign keys** (`PRAGMA foreign_keys=ON`) -- enforces referential integrity

These PRAGMAs are set via a SQLAlchemy `connect` event listener in `src/hive/store/db.py`.

The `db_url` config field allows connecting to databases other than SQLite (e.g., PostgreSQL) for future use.

## Two Databases, Same Schema

| Database | Default Path | Purpose |
|----------|-------------|---------|
| `store.db` | `~/.local/share/hive/store.db` | Local client store -- captures from your machine |
| `server.db` | `~/.local/share/hive/server.db` | Team server store -- receives pushed sessions from all team members |

Both use the identical schema defined in `src/hive/store/models.py` and managed by Alembic migrations. The server database is only used when running `hive serve`.

## Schema

Six tables plus supporting indexes:

### Core Tables

**`sessions`** -- One row per AI coding session.

**`messages`** -- Individual conversation turns, ordered by `ordinal`. Role is constrained to `human`, `assistant`, or `tool`.

**`enrichments`** -- Key-value metadata produced by enrichers. Keyed by `(session_id, source, key)`.

**`annotations`** -- User-created labels. Type is constrained to `tag`, `comment`, or `rating`.

**`edges`** -- Typed graph relationships linking sessions to files, commits, and other entities.

**`sessions_fts`** -- FTS5 virtual table for full-text search with Porter stemming.

!!! info "FTS5 with Porter Stemming"
    The `sessions_fts` table uses `tokenize='porter'`, which means searching for "refactoring" also matches "refactor" and "refactored". Search results include highlighted snippets via FTS5's `snippet()` function.

### Indexes

```sql
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_enrichments_session ON enrichments(session_id);
CREATE INDEX idx_enrichments_key ON enrichments(session_id, key);
CREATE INDEX idx_annotations_session ON annotations(session_id);
CREATE INDEX idx_edges_source ON edges(source_type, source_id);
CREATE INDEX idx_edges_target ON edges(target_type, target_id);
CREATE INDEX idx_sessions_project ON sessions(project_path);
CREATE INDEX idx_sessions_started ON sessions(started_at);
```

## QueryAPI

The `QueryAPI` class in `src/hive/store/query.py` is the single abstraction for all database access. No other code touches SQLite directly.

### Read Operations

| Method | Description |
|--------|-------------|
| `list_sessions()` | Filter/sort sessions by source, project, author, date range, tag, tokens, model, correction rate |
| `search_sessions()` | Full-text search via configured backend, falling back to FTS5 |
| `get_session()` | Single session with enrichments, annotations, file edges. Optionally includes messages. |
| `get_lineage()` | Walk the edges graph for a file path or session ID |
| `get_stats()` | Aggregated statistics, optionally grouped by project/model/author/week |
| `get_token_stats()` | Aggregate token usage across sessions |
| `list_projects()` | Distinct projects with session counts and activity dates |

### Write Operations

| Method | Description |
|--------|-------------|
| `upsert_session()` | Insert or update session metadata (ON CONFLICT updates ended_at, message_count, summary) |
| `insert_messages()` | Batch insert messages (INSERT OR IGNORE) |
| `insert_enrichment()` | Add a single enrichment key-value pair |
| `insert_edge()` | Create a typed edge relationship |
| `index_session_fts()` | Add session content to the FTS5 index |
| `write_annotation()` | Add a tag, comment, or rating |

### Delete

`delete_session()` performs a **cascading delete** across all six tables: messages, enrichments, annotations, edges, FTS index, and the session row itself. Also removes the session from the search backend if available.

### Export / Import

| Method | Description |
|--------|-------------|
| `export_session()` | Package a session with all messages, enrichments, annotations, and edges for pushing |
| `import_session()` | Receive a pushed payload. Clears existing data first (handles re-push), then inserts everything. |

!!! note "Idempotent Import"
    `import_session` deletes all existing data for the session ID before inserting. This makes re-push safe -- pushing the same session twice produces identical results.

## Pluggable Search Backends

Session search supports three backends, selected via `search_backend` in config:

=== "sqlite-vec (default)"
    In-process vector search using the `sqlite-vec` extension. No external server required. Embeddings are stored in a separate SQLite database (`search_vec.db`). Best for solo use and small teams.

=== "witchcraft"
    External semantic search server for advanced embedding-based search. Requires a running `hive-search` binary. Best for larger teams needing high-quality semantic retrieval.

=== "FTS5 fallback"
    Pure SQLite FTS5 keyword search with Porter stemming. Always available as the ultimate fallback when neither vector backend is configured or reachable.

The search flow: try the configured backend first, fall back to FTS5 on any error.

## Directory Permissions

The data directory (`~/.local/share/hive/`) is created with mode `0o700` (owner read/write/execute only), ensuring other users on the system cannot access your session data.
