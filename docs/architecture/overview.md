# Architecture Overview

hive uses a four-layer pipeline to turn raw AI coding sessions into searchable, shareable team knowledge.

## Four-Layer Pipeline

```mermaid
flowchart TB
    subgraph Capture
        A1[Claude Code hooks]
        A2[git post-commit hook]
    end
    subgraph Enrich
        B1[GitEnricher]
        B2[FilesEnricher]
        B3[QualityEnricher]
    end
    subgraph Store
        C1[(store.db<br/>SQLite + FTS5)]
        C2[(server.db)]
    end
    subgraph Serve
        D1[CLI]
        D2[REST API]
        D3[MCP server]
    end
    Capture --> Enrich --> Store --> Serve
    C1 -->|auto-push| C2
```

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| **Capture** | Claude Code hooks, git post-commit | Ingest raw session data from stdin JSON |
| **Enrich** | Git, Files, Quality enrichers | Attach derived metadata (branch, files, quality signals) |
| **Store** | SQLite + FTS5 (`store.db`, `server.db`) | Persist sessions, messages, enrichments, edges |
| **Serve** | CLI, REST API, MCP server | Query and expose data to humans and AI |

## Solo Mode (default)

Everything stays on your machine. Claude Code hooks capture sessions into a local SQLite database, and the MCP server reads directly from it.

```mermaid
flowchart LR
    CC[Claude Code] -->|hooks: SessionStart, Stop| CA[Capture Adapter]
    CA --> E[Enrich]
    E --> DB[(store.db)]
    DB --> CLI[hive CLI]
    DB --> MCP[MCP Server]
    MCP -->|search, recent, lineage| Claude[Claude Code / Desktop]
```

- Sessions are written to `store.db` (`~/.local/share/hive/store.db`)
- The CLI reads and writes `store.db` directly
- The MCP server queries `store.db` via `QueryAPI` — no network calls
- Nothing leaves your machine

## Team Mode

Enable per-project sharing to push sessions to a shared server. Local capture still works the same — team mode adds an auto-push step and routes MCP queries to the server.

```mermaid
flowchart LR
    subgraph DevA[Developer A]
        CA_A[Capture] --> DB_A[(store.db)]
        MCP_A[MCP Server]
    end
    subgraph DevB[Developer B]
        CA_B[Capture] --> DB_B[(store.db)]
        MCP_B[MCP Server]
    end
    subgraph Server[Team Server]
        SRV[(server.db)] --> API[REST API]
    end
    DB_A -->|auto-push on Stop| API
    DB_B -->|auto-push on Stop| API
    MCP_A -->|search, recent| API
    MCP_B -->|search, recent| API
```

- Enable with `hive config sharing on` and set `server_url` in `~/.config/hive/config.toml`
- When a session ends (`Stop` hook), the adapter scrubs secrets and POSTs the payload to the team server via a background thread
- MCP queries for shared projects route to the team server; unshared projects still query local `store.db`
- If the team server is unreachable, MCP falls back to local automatically

Transitioning from solo to team is one config change — the `server_url`.

## Two Databases

| Database | Path | Purpose |
|----------|------|---------|
| `store.db` | `~/.local/share/hive/store.db` | Local session data. Written by capture adapters and enrichers. Read by CLI commands. |
| `server.db` | `~/.local/share/hive/server.db` | Team server data. Written by the REST API `POST /api/sessions`. Read by the REST API and MCP server. |

Both use the same schema: `sessions`, `messages`, `enrichments`, `annotations`, `edges`, and `sessions_fts` (FTS5).

## Key Design Decisions

!!! abstract "1. Scrub on the client"
    Secrets are redacted using regex patterns _before_ data leaves the local
    machine. The `scrub()` function runs during JSONL parsing (content) and
    again via `scrub_payload()` before any push to the server. Patterns are
    configurable in `config.toml`.

!!! abstract "2. MCP reads from REST, not SQLite"
    The MCP server uses `httpx` to call the REST API rather than importing the
    SQLite layer. This means it works identically against localhost (solo) or a
    remote team server -- just change `server_url`. In solo mode, it can also
    read directly from local SQLite when no server is running.

!!! abstract "3. Daemon thread push"
    Auto-push to the team server happens in a `threading.Thread(daemon=True)`
    so the Claude Code hook returns immediately. If the push fails, it is
    silently dropped (logged at debug level).

!!! abstract "4. Edges graph for lineage"
    File and commit relationships are stored as typed edges
    (`session -> file`, `session -> commit`) rather than columns, enabling
    flexible lineage queries without schema changes.

!!! abstract "5. Idempotent setup"
    `hive init` and all hook installations are safe to run repeatedly. Hooks
    check for existing entries before adding. Session import uses
    `ON CONFLICT` upserts and clears-then-reinserts for re-pushes.

## Database Schema

| Table | Purpose |
|-------|---------|
| `sessions` | Session metadata (id, source, project, author, timestamps, summary) |
| `messages` | Individual messages (role, content, tool_name, ordinal, timestamp) |
| `enrichments` | Key-value context from enrichers (source, key, value) |
| `annotations` | User-applied metadata (tags, comments, ratings) |
| `edges` | Lineage graph (source_type/id to target_type/id + relationship) |
| `sessions_fts` | FTS5 full-text search index |

## Tech Stack

**Backend**: Python 3.11+, Click, FastAPI, SQLAlchemy 2.0, Alembic, SQLite (WAL mode), MCP SDK, httpx
