"""SQLite database initialization and schema management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hive.config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    project_path TEXT,
    author TEXT,
    started_at DATETIME,
    ended_at DATETIME,
    message_count INTEGER DEFAULT 0,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    ordinal INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('human', 'assistant', 'tool')),
    content TEXT,
    tool_name TEXT,
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    enriched_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    type TEXT NOT NULL CHECK(type IN ('tag', 'comment', 'rating')),
    value TEXT NOT NULL,
    author TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
    session_id,
    content,
    tokenize='porter'
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_enrichments_session ON enrichments(session_id);
CREATE INDEX IF NOT EXISTS idx_enrichments_key ON enrichments(session_id, key);
CREATE INDEX IF NOT EXISTS idx_annotations_session ON annotations(session_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
"""


def get_connection(config: Config | None = None, db_path: Path | None = None) -> sqlite3.Connection:
    if config is None:
        config = Config.load()
    path = db_path or config.db_path
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(config: Config | None = None, db_path: Path | None = None) -> sqlite3.Connection:
    if config is None:
        config = Config.load()
    path = db_path or config.db_path
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = get_connection(config, db_path=path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
