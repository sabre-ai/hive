"""Shared internal query API — all consumers wrap this."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hive.config import Config
from hive.store.db import get_connection


class QueryAPI:
    def __init__(self, config: Config | None = None, db_path: Path | None = None):
        self.config = config or Config.load()
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self.config, db_path=self._db_path)

    # ── List / filter sessions ──────────────────────────────────────

    def list_sessions(
        self,
        source: str | None = None,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        tag: str | None = None,
        sort_by: str | None = None,
        min_tokens: int | None = None,
        model: str | None = None,
        min_correction_rate: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        joins: list[str] = []

        if source:
            clauses.append("s.source = ?")
            params.append(source)
        if project:
            clauses.append("s.project_path LIKE ?")
            params.append(f"%{project}%")
        if author:
            clauses.append("s.author = ?")
            params.append(author)
        if since:
            clauses.append("s.started_at >= ?")
            params.append(since)
        if until:
            clauses.append("s.started_at <= ?")
            params.append(until)
        if tag:
            clauses.append(
                "EXISTS (SELECT 1 FROM annotations a2 WHERE a2.session_id = s.id AND a2.type = 'tag' AND a2.value = ?)"
            )
            params.append(tag)

        # Enrichment-based filters
        if min_tokens is not None:
            joins.append(
                "JOIN enrichments e_tok ON e_tok.session_id = s.id AND e_tok.source = 'tokens' AND e_tok.key = 'total_tokens'"
            )
            clauses.append("CAST(e_tok.value AS INTEGER) >= ?")
            params.append(min_tokens)
        if model:
            joins.append(
                "JOIN enrichments e_mod ON e_mod.session_id = s.id AND e_mod.source = 'tokens' AND e_mod.key = 'model'"
            )
            clauses.append("e_mod.value = ?")
            params.append(model)
        if min_correction_rate is not None:
            joins.append(
                "JOIN enrichments e_cf ON e_cf.session_id = s.id AND e_cf.source = 'quality' AND e_cf.key = 'correction_frequency'"
            )
            clauses.append("CAST(e_cf.value AS REAL) >= ?")
            params.append(min_correction_rate)

        # Sort by enrichment value
        order = "s.started_at DESC"
        if sort_by == "tokens":
            if "e_tok" not in " ".join(joins):
                joins.append(
                    "LEFT JOIN enrichments e_tok ON e_tok.session_id = s.id AND e_tok.source = 'tokens' AND e_tok.key = 'total_tokens'"
                )
            order = "CAST(e_tok.value AS INTEGER) DESC"
        elif sort_by == "corrections":
            if "e_cf" not in " ".join(joins):
                joins.append(
                    "LEFT JOIN enrichments e_cf ON e_cf.session_id = s.id AND e_cf.source = 'quality' AND e_cf.key = 'correction_frequency'"
                )
            order = "CAST(e_cf.value AS REAL) DESC"
        elif sort_by == "messages":
            order = "s.message_count DESC"

        join_sql = "\n".join(joins)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])

        conn = self._conn()
        rows = conn.execute(
            f"""
            SELECT s.*, GROUP_CONCAT(DISTINCT a.value) as tags
            FROM sessions s
            LEFT JOIN annotations a ON a.session_id = s.id AND a.type = 'tag'
            {join_sql}
            {where}
            GROUP BY s.id
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Full-text search ────────────────────────────────────────────

    def _get_search_backend(self):
        """Return the configured search backend, or None if unavailable."""
        if not hasattr(self, "_search_backend"):
            try:
                from hive.search import get_search_backend

                backend = get_search_backend(self.config)
                self._search_backend = backend if backend.is_available() else None
            except Exception:
                self._search_backend = None
        return self._search_backend

    def search_sessions(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search sessions via the configured semantic backend, falling back to FTS5."""
        try:
            backend = self._get_search_backend()
            if backend is not None:
                return self._search_semantic(backend, query, project, author, since, until, limit)
        except Exception:
            pass

        return self._search_fts5(query, project, author, since, until, limit)

    def _search_semantic(
        self,
        backend: Any,
        query: str,
        project: str | None,
        author: str | None,
        since: str | None,
        until: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search via the semantic backend and join with hive metadata."""
        results = backend.search(
            query, project=project, author=author, since=since, until=until, limit=limit
        )
        if not results:
            return []

        # Extract session IDs from metadata and look up full session data
        session_ids = []
        result_map: dict[str, dict[str, Any]] = {}
        for item in results:
            meta = item.get("metadata", {})
            sid = meta.get("session_id", "")
            if sid and sid not in result_map:
                session_ids.append(sid)
                result_map[sid] = item

        if not session_ids:
            return []

        # Batch lookup sessions from hive's store.db
        conn = self._conn()
        placeholders = ",".join("?" for _ in session_ids)
        rows = conn.execute(
            f"SELECT * FROM sessions WHERE id IN ({placeholders})",
            session_ids,
        ).fetchall()
        conn.close()

        # Merge hive metadata with witchcraft scores
        output = []
        for row in rows:
            session = dict(row)
            sid = session["id"]
            wc = result_map.get(sid, {})
            # Use matched body chunk as snippet, trimmed
            body = wc.get("body", "")
            snippet = body[:200] + "…" if len(body) > 200 else body
            session["snippet"] = snippet
            session["score"] = wc.get("score", 0.0)
            output.append(session)

        # Sort by witchcraft score (descending)
        output.sort(key=lambda s: s.get("score", 0.0), reverse=True)
        return output

    def _search_fts5(
        self,
        query: str,
        project: str | None,
        author: str | None,
        since: str | None,
        until: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fall back to SQLite FTS5 keyword search."""
        conn = self._conn()
        clauses = []
        params: list[Any] = [query]

        if project:
            clauses.append("AND s.project_path LIKE ?")
            params.append(f"%{project}%")
        if author:
            clauses.append("AND s.author = ?")
            params.append(author)
        if since:
            clauses.append("AND s.started_at >= ?")
            params.append(since)
        if until:
            clauses.append("AND s.started_at <= ?")
            params.append(until)

        extra = " ".join(clauses)
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT s.*, snippet(sessions_fts, 1, '<mark>', '</mark>', '…', 32) as snippet
            FROM sessions_fts fts
            JOIN sessions s ON s.id = fts.session_id
            WHERE sessions_fts MATCH ?
            {extra}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Get single session ──────────────────────────────────────────

    def get_session(
        self,
        session_id: str,
        detail: str | None = None,
        role: str | None = None,
        msg_limit: int | None = None,
        msg_offset: int = 0,
    ) -> dict[str, Any] | None:
        conn = self._conn()
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            conn.close()
            return None

        # Always include enrichments (lightweight)
        enrichments = conn.execute(
            "SELECT * FROM enrichments WHERE session_id = ? ORDER BY enriched_at",
            (session_id,),
        ).fetchall()

        annotations = conn.execute(
            "SELECT * FROM annotations WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()

        # Compute message stats (cheap aggregate, no content transfer)
        msg_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN role = 'human' THEN 1 ELSE 0 END) as human_count,
                SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) as assistant_count,
                SUM(CASE WHEN role = 'tool' THEN 1 ELSE 0 END) as tool_count
            FROM messages WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        # Flatten enrichments into a dict for easy access
        enrichment_dict = {}
        for e in enrichments:
            key = f"{e['source']}/{e['key']}"
            enrichment_dict[key] = e["value"]

        # Get files touched from edges
        files = conn.execute(
            "SELECT DISTINCT target_id FROM edges WHERE source_type = 'session' AND source_id = ? AND target_type = 'file'",
            (session_id,),
        ).fetchall()

        result: dict[str, Any] = {
            **dict(session),
            "enrichments": enrichment_dict,
            "enrichments_raw": [dict(e) for e in enrichments],
            "annotations": [dict(a) for a in annotations],
            "human_message_count": msg_stats["human_count"] or 0,
            "assistant_message_count": msg_stats["assistant_count"] or 0,
            "tool_message_count": msg_stats["tool_count"] or 0,
            "files_touched": [f["target_id"] for f in files],
        }

        # Only include messages if detail="messages"
        if detail == "messages":
            msg_clauses = ["session_id = ?"]
            msg_params: list[Any] = [session_id]

            if role:
                msg_clauses.append("role = ?")
                msg_params.append(role)

            msg_where = " AND ".join(msg_clauses)
            limit_sql = ""
            if msg_limit is not None:
                limit_sql = f"LIMIT {int(msg_limit)} OFFSET {int(msg_offset)}"

            messages = conn.execute(
                f"SELECT * FROM messages WHERE {msg_where} ORDER BY ordinal {limit_sql}",
                msg_params,
            ).fetchall()
            result["messages"] = [dict(m) for m in messages]

        conn.close()
        return result

    # ── Lineage ─────────────────────────────────────────────────────

    def get_lineage(self, identifier: str, id_type: str = "file") -> list[dict[str, Any]]:
        """Walk edges graph for a file path or session ID.

        For files, returns one row per session that touched the file,
        with associated commit SHAs aggregated.
        """
        conn = self._conn()
        if id_type == "file":
            # Find sessions linked to this file, plus any commits those sessions produced
            rows = conn.execute(
                """
                SELECT
                    s.id as session_id,
                    s.summary,
                    s.started_at,
                    s.author,
                    GROUP_CONCAT(DISTINCT e_file.relationship) as relationships,
                    GROUP_CONCAT(DISTINCT e_commit.target_id) as commit_shas
                FROM edges e_file
                JOIN sessions s ON e_file.source_type = 'session' AND s.id = e_file.source_id
                LEFT JOIN edges e_commit ON (
                    e_commit.source_type = 'session'
                    AND e_commit.source_id = s.id
                    AND e_commit.target_type = 'commit'
                )
                WHERE e_file.target_type = 'file' AND e_file.target_id = ?
                GROUP BY s.id
                ORDER BY s.started_at DESC
                """,
                (identifier,),
            ).fetchall()
        else:
            # Session-based: return all connected edges
            rows = conn.execute(
                """
                SELECT
                    e.*,
                    s.summary,
                    s.started_at,
                    s.author
                FROM edges e
                LEFT JOIN sessions s ON (
                    (e.source_type = 'session' AND s.id = e.source_id) OR
                    (e.target_type = 'session' AND s.id = e.target_id)
                )
                WHERE (e.source_type = 'session' AND e.source_id = ?)
                   OR (e.target_type = 'session' AND e.target_id = ?)
                ORDER BY e.created_at DESC
                """,
                (identifier, identifier),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        conn = self._conn()
        clauses: list[str] = []
        params: list[Any] = []
        if project:
            clauses.append("s.project_path LIKE ?")
            params.append(f"%{project}%")
        if since:
            clauses.append("s.started_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        # Grouped stats
        if group_by in ("project", "model", "author", "week"):
            if group_by == "project":
                group_col = "s.project_path"
                group_label = "project"
            elif group_by == "model":
                group_col = "e_model.value"
                group_label = "model"
            elif group_by == "author":
                group_col = "s.author"
                group_label = "author"
            elif group_by == "week":
                group_col = "strftime('%Y-W%W', s.started_at)"
                group_label = "week"

            model_join = ""
            if group_by == "model":
                model_join = "LEFT JOIN enrichments e_model ON e_model.session_id = s.id AND e_model.source = 'tokens' AND e_model.key = 'model'"

            # Get token totals per group
            rows = conn.execute(
                f"""
                SELECT
                    {group_col} as group_key,
                    COUNT(DISTINCT s.id) as total_sessions,
                    SUM(s.message_count) as total_messages,
                    AVG(s.message_count) as avg_messages,
                    MIN(s.started_at) as earliest,
                    MAX(s.started_at) as latest
                FROM sessions s
                {model_join}
                {where}
                GROUP BY group_key
                ORDER BY total_sessions DESC
                """,
                params,
            ).fetchall()

            results = []
            for r in rows:
                group_key = r["group_key"]
                entry: dict[str, Any] = {
                    group_label: group_key,
                    "total_sessions": r["total_sessions"],
                    "total_messages": r["total_messages"],
                    "avg_messages": r["avg_messages"],
                    "earliest": r["earliest"],
                    "latest": r["latest"],
                }

                # Get token totals for this group
                if group_by == "model":
                    tok_rows = conn.execute(
                        """
                        SELECT SUM(CAST(e2.value AS INTEGER)) as total_tokens
                        FROM enrichments e2
                        JOIN enrichments e_m ON e_m.session_id = e2.session_id AND e_m.source = 'tokens' AND e_m.key = 'model' AND e_m.value = ?
                        WHERE e2.source = 'tokens' AND e2.key = 'total_tokens'
                        """,
                        (group_key,),
                    ).fetchone()
                    entry["total_tokens"] = tok_rows["total_tokens"] if tok_rows else 0
                results.append(entry)

            conn.close()
            return results

        # Flat stats (existing behavior)
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) as total_sessions,
                AVG(s.message_count) as avg_messages,
                SUM(s.message_count) as total_messages,
                MIN(s.started_at) as earliest,
                MAX(s.started_at) as latest
            FROM sessions s {where}
            """,
            params,
        ).fetchone()

        # Gather quality enrichments
        quality_params = list(params)
        quality_rows = conn.execute(
            f"""
            SELECT e.key, AVG(CAST(e.value AS REAL)) as avg_val,
                   SUM(CAST(e.value AS REAL)) as sum_val
            FROM enrichments e
            JOIN sessions s ON s.id = e.session_id
            {where + " AND" if where else "WHERE"} e.source = 'quality'
            GROUP BY e.key
            """,
            quality_params,
        ).fetchall()

        conn.close()
        result = dict(row) if row else {}
        result["quality"] = {
            r["key"]: {"avg": r["avg_val"], "total": r["sum_val"]} for r in quality_rows
        }
        return result

    # ── Token usage ──────────────────────────────────────────────────

    def get_session_tokens(self, session_id: str) -> dict[str, str]:
        """Return token enrichments for a session as a dict."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT key, value FROM enrichments WHERE session_id = ? AND source = 'tokens'",
            (session_id,),
        ).fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}

    def get_token_stats(
        self, project: str | None = None, since: str | None = None
    ) -> dict[str, Any]:
        """Aggregate token usage across sessions."""
        conn = self._conn()
        clauses = ["e.source = 'tokens'", "e.key != 'model'"]
        params: list[Any] = []
        if project:
            clauses.append("s.project_path LIKE ?")
            params.append(f"%{project}%")
        if since:
            clauses.append("s.started_at >= ?")
            params.append(since)
        where = "WHERE " + " AND ".join(clauses)

        rows = conn.execute(
            f"""
            SELECT e.key, SUM(CAST(e.value AS INTEGER)) as total
            FROM enrichments e
            JOIN sessions s ON s.id = e.session_id
            {where}
            GROUP BY e.key
            """,
            params,
        ).fetchall()
        conn.close()
        return {r["key"]: r["total"] for r in rows}

    # ── Projects ─────────────────────────────────────────────────────

    def list_projects(self) -> list[dict[str, Any]]:
        """Return distinct projects with session counts and last activity."""
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT
                project_path,
                COUNT(*) as session_count,
                SUM(message_count) as total_messages,
                MAX(started_at) as last_active,
                MIN(started_at) as first_active
            FROM sessions
            WHERE project_path IS NOT NULL AND project_path != ''
            GROUP BY project_path
            ORDER BY last_active DESC
            """
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Annotations ─────────────────────────────────────────────────

    def write_annotation(
        self,
        session_id: str,
        ann_type: str,
        value: str,
        author: str = "user",
    ) -> int:
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO annotations (session_id, type, value, author) VALUES (?, ?, ?, ?)",
            (session_id, ann_type, value, author),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    # ── Write helpers (used by capture/enrich) ──────────────────────

    def upsert_session(self, session: dict[str, Any]) -> None:
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO sessions (id, source, project_path, author, started_at, ended_at, message_count, summary)
            VALUES (:id, :source, :project_path, :author, :started_at, :ended_at, :message_count, :summary)
            ON CONFLICT(id) DO UPDATE SET
                ended_at = excluded.ended_at,
                message_count = excluded.message_count,
                summary = COALESCE(excluded.summary, sessions.summary)
            """,
            session,
        )
        conn.commit()
        conn.close()

    def insert_messages(self, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        conn = self._conn()
        conn.executemany(
            """
            INSERT OR IGNORE INTO messages (session_id, ordinal, role, content, tool_name, timestamp)
            VALUES (:session_id, :ordinal, :role, :content, :tool_name, :timestamp)
            """,
            messages,
        )
        conn.commit()
        conn.close()

    def insert_enrichment(self, session_id: str, source: str, key: str, value: str) -> None:
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO enrichments (session_id, source, key, value)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, source, key, value),
        )
        conn.commit()
        conn.close()

    def insert_edge(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship: str,
    ) -> None:
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO edges (source_type, source_id, target_type, target_id, relationship)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_type, source_id, target_type, target_id, relationship),
        )
        conn.commit()
        conn.close()

    def index_session_fts(self, session_id: str, content: str) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT INTO sessions_fts (session_id, content) VALUES (?, ?)",
            (session_id, content),
        )
        conn.commit()
        conn.close()

    # ── Delete ──────────────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        """Cascading delete of a session and all related data."""
        conn = self._conn()
        # Check existence first
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            conn.close()
            return False

        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM enrichments WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM annotations WHERE session_id = ?", (session_id,))
        conn.execute(
            "DELETE FROM edges WHERE source_type = 'session' AND source_id = ?",
            (session_id,),
        )
        # FTS5 contentless table: delete by rowid via session_id match
        conn.execute("DELETE FROM sessions_fts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

        # Remove from search backend
        try:
            backend = self._get_search_backend()
            if backend is not None:
                backend.remove_document(session_id)
        except Exception:
            pass

        return True

    # ── Export / Import (for push to server) ─────────────────────────

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export a full session payload suitable for pushing to the server."""
        data = self.get_session(session_id, detail="messages")
        if not data:
            return None
        conn = self._conn()
        edges = conn.execute(
            "SELECT * FROM edges WHERE source_type = 'session' AND source_id = ?",
            (session_id,),
        ).fetchall()
        conn.close()
        data["edges"] = [dict(e) for e in edges]
        # Server expects enrichments as list[dict] with source/key/value fields
        data["enrichments"] = data.pop("enrichments_raw", [])
        return data

    def import_session(self, payload: dict[str, Any]) -> None:
        """Import a full session payload (from a client push). Handles re-push."""
        session_id = payload["id"]
        conn = self._conn()

        # Clear existing data for this session (handles re-push)
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM enrichments WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM annotations WHERE session_id = ?", (session_id,))
        conn.execute(
            "DELETE FROM edges WHERE source_type = 'session' AND source_id = ?",
            (session_id,),
        )
        conn.execute("DELETE FROM sessions_fts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        # Insert session
        conn.execute(
            """
            INSERT INTO sessions (id, source, project_path, author, started_at, ended_at, message_count, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.get("source", ""),
                payload.get("project_path"),
                payload.get("author"),
                payload.get("started_at"),
                payload.get("ended_at"),
                payload.get("message_count", 0),
                payload.get("summary"),
            ),
        )

        # Insert messages
        for msg in payload.get("messages", []):
            conn.execute(
                """
                INSERT INTO messages (session_id, ordinal, role, content, tool_name, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    msg.get("ordinal", 0),
                    msg.get("role", "human"),
                    msg.get("content"),
                    msg.get("tool_name"),
                    msg.get("timestamp"),
                ),
            )

        # Insert enrichments
        for e in payload.get("enrichments", []):
            conn.execute(
                "INSERT INTO enrichments (session_id, source, key, value) VALUES (?, ?, ?, ?)",
                (session_id, e.get("source", ""), e.get("key", ""), e.get("value")),
            )

        # Insert annotations
        for a in payload.get("annotations", []):
            conn.execute(
                "INSERT INTO annotations (session_id, type, value, author) VALUES (?, ?, ?, ?)",
                (session_id, a.get("type", "tag"), a.get("value", ""), a.get("author")),
            )

        # Insert edges
        for edge in payload.get("edges", []):
            conn.execute(
                "INSERT INTO edges (source_type, source_id, target_type, target_id, relationship) VALUES (?, ?, ?, ?, ?)",
                (
                    edge.get("source_type", ""),
                    edge.get("source_id", ""),
                    edge.get("target_type", ""),
                    edge.get("target_id", ""),
                    edge.get("relationship", ""),
                ),
            )

        # Index for FTS
        fts_parts = [
            msg.get("content", "") for msg in payload.get("messages", []) if msg.get("content")
        ]
        if fts_parts:
            conn.execute(
                "INSERT INTO sessions_fts (session_id, content) VALUES (?, ?)",
                (session_id, "\n".join(fts_parts)),
            )

        conn.commit()
        conn.close()

        # Index in search backend
        try:
            from hive.search import build_metadata, build_search_body

            backend = self._get_search_backend()
            if backend is not None:
                messages_for_search = [
                    {"role": m.get("role", "human"), "content": m.get("content", "")}
                    for m in payload.get("messages", [])
                    if m.get("content")
                ]
                body, chunk_lengths = build_search_body(messages_for_search)
                if body:
                    metadata = build_metadata(payload)
                    backend.add_document(
                        session_id, payload.get("started_at"), metadata, body, chunk_lengths
                    )
                    backend.trigger_index(limit=1)
        except Exception:
            pass
