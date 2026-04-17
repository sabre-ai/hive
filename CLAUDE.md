# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hive is a team server for Claude Code that captures AI coding sessions, enriches them with context (git, file paths, quality metrics), stores them in SQLite, and makes them searchable via CLI, REST API, and MCP. Supports solo (local) and team (shared server) modes.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a single test file or test
pytest tests/test_store.py -v
pytest tests/test_store.py::test_function_name -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Format check (CI uses this)
ruff format --check src/ tests/

# Start the server
hive serve --port 3000

# Start MCP server (stdio)
hive mcp
```

## Architecture

Four-layer pipeline: **Capture → Enrich → Store → Serve**

```
src/hive/
├── capture/        # Adapters that ingest session data
│   ├── base.py     # CaptureAdapter protocol
│   ├── claude_code.py  # Main adapter: parses Claude Code hook JSON from stdin
│   └── git_hook.py     # Post-commit hook linkage
├── enrich/         # Enrichers that add context to sessions
│   ├── base.py     # Enricher protocol: name(), should_run(), run() → dict
│   ├── git.py      # Branch, commit, remote, diff stat
│   ├── files.py    # File path extraction from messages
│   └── quality.py  # Message counts, human/assistant ratio, corrections, duration
├── store/          # SQLite persistence (WAL mode, FTS5 full-text search)
│   ├── db.py       # Schema (sessions, messages, enrichments, annotations, edges, sessions_fts)
│   └── query.py    # QueryAPI — single abstraction for all DB reads/writes
├── serve/
│   └── api.py      # FastAPI REST API
├── mcp_server.py   # MCP server (6 tools: search, get_session, lineage, recent, stats, delete)
├── cli.py          # Click CLI (init, serve, search, show, log, lineage, stats, push, etc.)
├── config.py       # TOML-based config (~/.hive/config.toml + per-project .hive/config.toml)
└── privacy.py      # Secret scrubbing (regex patterns from scrub_patterns.toml)
```

**Key patterns:**
- `CaptureAdapter` protocol in `capture/base.py` — extensible for future adapters (Cursor, Copilot, etc.)
- `Enricher` protocol in `enrich/base.py` — plug in new enrichers by implementing `name()`, `should_run()`, `run()`
- `QueryAPI` in `store/query.py` — all DB access goes through this single class
- Two databases: `~/.hive/store.db` (local client) and `~/.hive/server.db` (team server)
- Auto-push to server runs in a daemon thread to avoid hook latency

## Code Style

- Python 3.11+, line length 100
- Ruff rules: E, F, I, UP, B, SIM (E501 and SIM105 ignored)
- Double quotes
- Pre-commit hooks run ruff check --fix and ruff format
