"""Shared internal query API — all consumers wrap this."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import case, cast, delete, distinct, func, select, text
from sqlalchemy.orm import Session

from hive.config import Config
from hive.store.db import get_engine, get_session_factory
from hive.store.models import Annotation, Edge, Enrichment, Message
from hive.store.models import Session as SessionModel


def _group_concat(col, dialect_name: str):
    """Dialect-aware GROUP_CONCAT / STRING_AGG for distinct values."""
    if dialect_name == "postgresql":
        return func.string_agg(distinct(cast(col, sa.Text)), ",")
    return func.group_concat(distinct(col))


class QueryAPI:
    def __init__(self, config: Config | None = None, db_path: Path | None = None):
        self.config = config or Config.load()
        self._db_path = db_path
        self._factory = get_session_factory(self.config, db_path)
        self._dialect = get_engine(self.config, db_path).dialect.name

    def _session(self) -> Session:
        return self._factory()

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
        S = SessionModel
        A = Annotation
        E = Enrichment

        with self._session() as session:
            # Base query with tag aggregation
            tag_sub = (
                select(A.session_id, _group_concat(A.value, self._dialect).label("tags"))
                .where(A.type == "tag")
                .group_by(A.session_id)
                .subquery()
            )

            q = select(S, tag_sub.c.tags).outerjoin(tag_sub, S.id == tag_sub.c.session_id)

            # Filters
            if source:
                q = q.where(S.source == source)
            if project:
                q = q.where(S.project_path.like(f"%{project}%"))
            if author:
                q = q.where(S.author == author)
            if since:
                q = q.where(S.started_at >= since)
            if until:
                q = q.where(S.started_at <= until)
            if tag:
                q = q.where(S.id.in_(select(A.session_id).where(A.type == "tag", A.value == tag)))

            # Enrichment-based filters via subqueries
            if min_tokens is not None:
                tok_sub = (
                    select(E.session_id)
                    .where(E.source == "tokens", E.key == "total_tokens")
                    .where(cast(E.value, sa.Integer) >= min_tokens)
                )
                q = q.where(S.id.in_(tok_sub))
            if model:
                mod_sub = select(E.session_id).where(
                    E.source == "tokens", E.key == "model", E.value == model
                )
                q = q.where(S.id.in_(mod_sub))
            if min_correction_rate is not None:
                cf_sub = (
                    select(E.session_id)
                    .where(E.source == "quality", E.key == "correction_frequency")
                    .where(cast(E.value, sa.Float) >= min_correction_rate)
                )
                q = q.where(S.id.in_(cf_sub))

            # Sorting
            if sort_by == "tokens":
                tok_sort = (
                    select(E.session_id, cast(E.value, sa.Integer).label("tok_val"))
                    .where(E.source == "tokens", E.key == "total_tokens")
                    .subquery()
                )
                q = q.outerjoin(tok_sort, S.id == tok_sort.c.session_id)
                q = q.order_by(tok_sort.c.tok_val.desc().nullslast())
            elif sort_by == "corrections":
                cf_sort = (
                    select(E.session_id, cast(E.value, sa.Float).label("cf_val"))
                    .where(E.source == "quality", E.key == "correction_frequency")
                    .subquery()
                )
                q = q.outerjoin(cf_sort, S.id == cf_sort.c.session_id)
                q = q.order_by(cf_sort.c.cf_val.desc().nullslast())
            elif sort_by == "messages":
                q = q.order_by(S.message_count.desc())
            else:
                q = q.order_by(S.started_at.desc())

            q = q.limit(limit).offset(offset)
            rows = session.execute(q).all()

            results = []
            for row in rows:
                s = row[0]
                d = {
                    "id": s.id,
                    "source": s.source,
                    "project_path": s.project_path,
                    "author": s.author,
                    "started_at": s.started_at,
                    "ended_at": s.ended_at,
                    "message_count": s.message_count,
                    "summary": s.summary,
                    "tags": row[1],
                }
                results.append(d)
            return results

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

        return self._search_fts(query, project, author, since, until, limit)

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

        with self._session() as session:
            rows = (
                session.execute(select(SessionModel).where(SessionModel.id.in_(session_ids)))
                .scalars()
                .all()
            )

        output = []
        for s in rows:
            d = _session_to_dict(s)
            wc = result_map.get(s.id, {})
            body = wc.get("body", "")
            d["snippet"] = body[:200] + "…" if len(body) > 200 else body
            d["score"] = wc.get("score", 0.0)
            output.append(d)

        output.sort(key=lambda s: s.get("score", 0.0), reverse=True)
        return output

    def _search_fts(
        self,
        query: str,
        project: str | None,
        author: str | None,
        since: str | None,
        until: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fall back to native full-text search (FTS5 on SQLite, tsvector on PostgreSQL)."""
        with self._session() as session:
            clauses = []
            params: dict[str, Any] = {"query": query, "limit": limit}

            if project:
                clauses.append("AND s.project_path LIKE :project")
                params["project"] = f"%{project}%"
            if author:
                clauses.append("AND s.author = :author")
                params["author"] = author
            if since:
                clauses.append("AND s.started_at >= :since")
                params["since"] = since
            if until:
                clauses.append("AND s.started_at <= :until")
                params["until"] = until

            extra = " ".join(clauses)

            if self._dialect == "postgresql":
                sql = f"""
                    SELECT s.*,
                           ts_rank(fts.search_vector, plainto_tsquery('english', :query)) AS rank,
                           ts_headline('english', fts.content, plainto_tsquery('english', :query),
                                       'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=32'
                           ) AS snippet
                    FROM sessions_fts_pg fts
                    JOIN sessions s ON s.id = fts.session_id
                    WHERE fts.search_vector @@ plainto_tsquery('english', :query)
                    {extra}
                    ORDER BY rank DESC
                    LIMIT :limit
                    """
            else:
                sql = f"""
                    SELECT s.*, snippet(sessions_fts, 1, '<mark>', '</mark>', '…', 32) as snippet
                    FROM sessions_fts fts
                    JOIN sessions s ON s.id = fts.session_id
                    WHERE sessions_fts MATCH :query
                    {extra}
                    ORDER BY rank
                    LIMIT :limit
                    """

            rows = session.execute(text(sql), params).mappings().all()
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
        with self._session() as session:
            s = session.get(SessionModel, session_id)
            if not s:
                return None

            enrichments = (
                session.execute(
                    select(Enrichment)
                    .where(Enrichment.session_id == session_id)
                    .order_by(Enrichment.enriched_at)
                )
                .scalars()
                .all()
            )

            annotations = (
                session.execute(
                    select(Annotation)
                    .where(Annotation.session_id == session_id)
                    .order_by(Annotation.created_at)
                )
                .scalars()
                .all()
            )

            # Message stats
            msg_stats = session.execute(
                select(
                    func.count().label("total"),
                    func.sum(case((Message.role == "human", 1), else_=0)).label("human_count"),
                    func.sum(case((Message.role == "assistant", 1), else_=0)).label(
                        "assistant_count"
                    ),
                    func.sum(case((Message.role == "tool", 1), else_=0)).label("tool_count"),
                ).where(Message.session_id == session_id)
            ).one()

            enrichment_dict = {}
            for e in enrichments:
                key = f"{e.source}/{e.key}"
                enrichment_dict[key] = e.value

            files = (
                session.execute(
                    select(distinct(Edge.target_id)).where(
                        Edge.source_type == "session",
                        Edge.source_id == session_id,
                        Edge.target_type == "file",
                    )
                )
                .scalars()
                .all()
            )

            result: dict[str, Any] = {
                **_session_to_dict(s),
                "enrichments": enrichment_dict,
                "enrichments_raw": [
                    {
                        "id": e.id,
                        "session_id": e.session_id,
                        "source": e.source,
                        "key": e.key,
                        "value": e.value,
                        "enriched_at": e.enriched_at,
                    }
                    for e in enrichments
                ],
                "annotations": [
                    {
                        "id": a.id,
                        "session_id": a.session_id,
                        "type": a.type,
                        "value": a.value,
                        "author": a.author,
                        "created_at": a.created_at,
                    }
                    for a in annotations
                ],
                "human_message_count": msg_stats.human_count or 0,
                "assistant_message_count": msg_stats.assistant_count or 0,
                "tool_message_count": msg_stats.tool_count or 0,
                "files_touched": list(files),
            }

            if detail == "messages":
                q = select(Message).where(Message.session_id == session_id)
                if role:
                    q = q.where(Message.role == role)
                q = q.order_by(Message.ordinal)
                if msg_limit is not None:
                    q = q.limit(msg_limit).offset(msg_offset)
                messages = session.execute(q).scalars().all()
                result["messages"] = [
                    {
                        "id": m.id,
                        "session_id": m.session_id,
                        "ordinal": m.ordinal,
                        "role": m.role,
                        "content": m.content,
                        "tool_name": m.tool_name,
                        "timestamp": m.timestamp,
                    }
                    for m in messages
                ]

            return result

    # ── Lineage ─────────────────────────────────────────────────────

    def get_lineage(self, identifier: str, id_type: str = "file") -> list[dict[str, Any]]:
        """Walk edges graph for a file path or session ID."""
        if self._dialect == "postgresql":
            agg_rel = "STRING_AGG(DISTINCT e_file.relationship, ',')"
            agg_commit = "STRING_AGG(DISTINCT e_commit.target_id, ',')"
        else:
            agg_rel = "GROUP_CONCAT(DISTINCT e_file.relationship)"
            agg_commit = "GROUP_CONCAT(DISTINCT e_commit.target_id)"

        with self._session() as session:
            if id_type == "file":
                rows = (
                    session.execute(
                        text(
                            f"""
                        SELECT
                            s.id as session_id,
                            s.summary,
                            s.started_at,
                            s.author,
                            {agg_rel} as relationships,
                            {agg_commit} as commit_shas
                        FROM edges e_file
                        JOIN sessions s ON e_file.source_type = 'session' AND s.id = e_file.source_id
                        LEFT JOIN edges e_commit ON (
                            e_commit.source_type = 'session'
                            AND e_commit.source_id = s.id
                            AND e_commit.target_type = 'commit'
                        )
                        WHERE e_file.target_type = 'file' AND e_file.target_id = :identifier
                        GROUP BY s.id
                        ORDER BY s.started_at DESC
                        """
                        ),
                        {"identifier": identifier},
                    )
                    .mappings()
                    .all()
                )
            else:
                rows = (
                    session.execute(
                        text(
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
                        WHERE (e.source_type = 'session' AND e.source_id = :id1)
                           OR (e.target_type = 'session' AND e.target_id = :id2)
                        ORDER BY e.created_at DESC
                        """
                        ),
                        {"id1": identifier, "id2": identifier},
                    )
                    .mappings()
                    .all()
                )

            return [dict(r) for r in rows]

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        S = SessionModel
        E = Enrichment

        with self._session() as session:
            filters = []
            if project:
                filters.append(S.project_path.like(f"%{project}%"))
            if since:
                filters.append(S.started_at >= since)

            if group_by in ("project", "model", "author", "week"):
                if group_by == "project":
                    group_col = S.project_path
                    group_label = "project"
                elif group_by == "author":
                    group_col = S.author
                    group_label = "author"
                elif group_by == "week":
                    if self._dialect == "postgresql":
                        group_col = func.to_char(S.started_at, 'IYYY-"W"IW')
                    else:
                        group_col = func.strftime("%Y-W%W", S.started_at)
                    group_label = "week"
                elif group_by == "model":
                    group_label = "model"
                    # Model comes from enrichments — use raw SQL for this complex case
                    return self._get_stats_grouped_by_model(session, filters)

                q = (
                    select(
                        group_col.label("group_key"),
                        func.count(distinct(S.id)).label("total_sessions"),
                        func.sum(S.message_count).label("total_messages"),
                        func.avg(S.message_count).label("avg_messages"),
                        func.min(S.started_at).label("earliest"),
                        func.max(S.started_at).label("latest"),
                    )
                    .where(*filters)
                    .group_by(group_col)
                    .order_by(func.count(distinct(S.id)).desc())
                )
                rows = session.execute(q).all()
                return [
                    {
                        group_label: r.group_key,
                        "total_sessions": r.total_sessions,
                        "total_messages": r.total_messages,
                        "avg_messages": float(r.avg_messages) if r.avg_messages else 0,
                        "earliest": r.earliest,
                        "latest": r.latest,
                    }
                    for r in rows
                ]

            # Flat stats
            row = session.execute(
                select(
                    func.count().label("total_sessions"),
                    func.avg(S.message_count).label("avg_messages"),
                    func.sum(S.message_count).label("total_messages"),
                    func.min(S.started_at).label("earliest"),
                    func.max(S.started_at).label("latest"),
                )
                .select_from(S)
                .where(*filters)
            ).one()

            quality_rows = session.execute(
                select(
                    E.key,
                    func.avg(cast(E.value, sa.Float)).label("avg_val"),
                    func.sum(cast(E.value, sa.Float)).label("sum_val"),
                )
                .join(S, S.id == E.session_id)
                .where(E.source == "quality", *filters)
                .group_by(E.key)
            ).all()

            result: dict[str, Any] = {
                "total_sessions": row.total_sessions,
                "avg_messages": float(row.avg_messages) if row.avg_messages else 0,
                "total_messages": row.total_messages or 0,
                "earliest": row.earliest,
                "latest": row.latest,
            }
            result["quality"] = {
                r.key: {
                    "avg": float(r.avg_val) if r.avg_val else 0,
                    "total": float(r.sum_val) if r.sum_val else 0,
                }
                for r in quality_rows
            }
            return result

    def _get_stats_grouped_by_model(self, session: Session, filters: list) -> list[dict[str, Any]]:
        """Group-by-model stats using enrichment join."""
        S = SessionModel
        E = Enrichment

        e_model = E.__table__.alias("e_model")
        q = (
            select(
                e_model.c.value.label("group_key"),
                func.count(distinct(S.id)).label("total_sessions"),
                func.sum(S.message_count).label("total_messages"),
                func.avg(S.message_count).label("avg_messages"),
                func.min(S.started_at).label("earliest"),
                func.max(S.started_at).label("latest"),
            )
            .select_from(S)
            .join(
                e_model,
                (e_model.c.session_id == S.id)
                & (e_model.c.source == "tokens")
                & (e_model.c.key == "model"),
            )
            .where(*filters)
            .group_by(e_model.c.value)
            .order_by(func.count(distinct(S.id)).desc())
        )
        rows = session.execute(q).all()

        results = []
        for r in rows:
            entry: dict[str, Any] = {
                "model": r.group_key,
                "total_sessions": r.total_sessions,
                "total_messages": r.total_messages,
                "avg_messages": float(r.avg_messages) if r.avg_messages else 0,
                "earliest": r.earliest,
                "latest": r.latest,
            }

            # Token totals for this model
            tok_row = session.execute(
                text(
                    """
                    SELECT SUM(CAST(e2.value AS INTEGER)) as total_tokens
                    FROM enrichments e2
                    JOIN enrichments e_m ON e_m.session_id = e2.session_id
                        AND e_m.source = 'tokens' AND e_m.key = 'model' AND e_m.value = :model
                    WHERE e2.source = 'tokens' AND e2.key = 'total_tokens'
                    """
                ),
                {"model": r.group_key},
            ).one()
            entry["total_tokens"] = tok_row.total_tokens or 0
            results.append(entry)

        return results

    # ── Token usage ──────────────────────────────────────────────────

    def get_session_tokens(self, session_id: str) -> dict[str, str]:
        """Return token enrichments for a session as a dict."""
        with self._session() as session:
            rows = session.execute(
                select(Enrichment.key, Enrichment.value).where(
                    Enrichment.session_id == session_id, Enrichment.source == "tokens"
                )
            ).all()
            return {r.key: r.value for r in rows}

    def get_token_stats(
        self, project: str | None = None, since: str | None = None
    ) -> dict[str, Any]:
        """Aggregate token usage across sessions."""
        S = SessionModel
        E = Enrichment

        with self._session() as session:
            filters = [E.source == "tokens", E.key != "model"]
            if project:
                filters.append(S.project_path.like(f"%{project}%"))
            if since:
                filters.append(S.started_at >= since)

            rows = session.execute(
                select(
                    E.key,
                    func.sum(cast(E.value, sa.Integer)).label("total"),
                )
                .join(S, S.id == E.session_id)
                .where(*filters)
                .group_by(E.key)
            ).all()
            return {r.key: r.total for r in rows}

    # ── Projects ─────────────────────────────────────────────────────

    def list_projects(self) -> list[dict[str, Any]]:
        """Return distinct projects with session counts and last activity."""
        S = SessionModel
        with self._session() as session:
            rows = session.execute(
                select(
                    S.project_path,
                    func.count().label("session_count"),
                    func.sum(S.message_count).label("total_messages"),
                    func.max(S.started_at).label("last_active"),
                    func.min(S.started_at).label("first_active"),
                )
                .where(S.project_path.isnot(None), S.project_path != "")
                .group_by(S.project_path)
                .order_by(func.max(S.started_at).desc())
            ).all()
            return [
                {
                    "project_path": r.project_path,
                    "session_count": r.session_count,
                    "total_messages": r.total_messages,
                    "last_active": str(r.last_active) if r.last_active else None,
                    "first_active": str(r.first_active) if r.first_active else None,
                }
                for r in rows
            ]

    # ── Annotations ─────────────────────────────────────────────────

    def write_annotation(
        self,
        session_id: str,
        ann_type: str,
        value: str,
        author: str = "user",
    ) -> int:
        with self._session() as session:
            ann = Annotation(session_id=session_id, type=ann_type, value=value, author=author)
            session.add(ann)
            session.commit()
            return ann.id

    # ── Write helpers (used by capture/enrich) ──────────────────────

    def upsert_session(self, data: dict[str, Any]) -> None:
        with self._session() as session:
            existing = session.get(SessionModel, data["id"])
            if existing:
                existing.ended_at = data.get("ended_at", existing.ended_at)
                existing.message_count = data.get("message_count", existing.message_count)
                existing.summary = data.get("summary") or existing.summary
            else:
                s = SessionModel(
                    id=data["id"],
                    source=data["source"],
                    project_path=data.get("project_path"),
                    author=data.get("author"),
                    started_at=data.get("started_at"),
                    ended_at=data.get("ended_at"),
                    message_count=data.get("message_count", 0),
                    summary=data.get("summary"),
                )
                session.add(s)
            session.commit()

    def insert_messages(self, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        with self._session() as session:
            for msg in messages:
                # Check for existing message to implement INSERT OR IGNORE
                existing = session.execute(
                    select(Message).where(
                        Message.session_id == msg["session_id"],
                        Message.ordinal == msg["ordinal"],
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        Message(
                            session_id=msg["session_id"],
                            ordinal=msg["ordinal"],
                            role=msg["role"],
                            content=msg.get("content"),
                            tool_name=msg.get("tool_name"),
                            timestamp=msg.get("timestamp"),
                        )
                    )
            session.commit()

    def insert_enrichment(self, session_id: str, source: str, key: str, value: str) -> None:
        with self._session() as session:
            session.add(Enrichment(session_id=session_id, source=source, key=key, value=value))
            session.commit()

    def insert_edge(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship: str,
    ) -> None:
        with self._session() as session:
            session.add(
                Edge(
                    source_type=source_type,
                    source_id=source_id,
                    target_type=target_type,
                    target_id=target_id,
                    relationship_=relationship,
                )
            )
            session.commit()

    def index_session_fts(self, session_id: str, content: str) -> None:
        """Index session content for full-text search."""
        with self._session() as session:
            if self._dialect == "postgresql":
                session.execute(
                    text(
                        "INSERT INTO sessions_fts_pg (session_id, content) "
                        "VALUES (:sid, :content) "
                        "ON CONFLICT (session_id) DO UPDATE SET content = EXCLUDED.content"
                    ),
                    {"sid": session_id, "content": content},
                )
            elif self._dialect == "sqlite":
                session.execute(
                    text("INSERT INTO sessions_fts (session_id, content) VALUES (:sid, :content)"),
                    {"sid": session_id, "content": content},
                )
            else:
                return
            session.commit()

    # ── Delete ──────────────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        """Cascading delete of a session and all related data."""
        with self._session() as session:
            s = session.get(SessionModel, session_id)
            if not s:
                return False

            session.execute(delete(Message).where(Message.session_id == session_id))
            session.execute(delete(Enrichment).where(Enrichment.session_id == session_id))
            session.execute(delete(Annotation).where(Annotation.session_id == session_id))
            session.execute(
                delete(Edge).where(Edge.source_type == "session", Edge.source_id == session_id)
            )
            if self._dialect == "sqlite":
                session.execute(
                    text("DELETE FROM sessions_fts WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            elif self._dialect == "postgresql":
                session.execute(
                    text("DELETE FROM sessions_fts_pg WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            session.execute(delete(SessionModel).where(SessionModel.id == session_id))
            session.commit()

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

        with self._session() as session:
            edges = (
                session.execute(
                    select(Edge).where(Edge.source_type == "session", Edge.source_id == session_id)
                )
                .scalars()
                .all()
            )
            data["edges"] = [
                {
                    "source_type": e.source_type,
                    "source_id": e.source_id,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "relationship": e.relationship_,
                    "created_at": e.created_at,
                }
                for e in edges
            ]
        data["enrichments"] = data.pop("enrichments_raw", [])
        return data

    def import_session(self, payload: dict[str, Any]) -> None:
        """Import a full session payload (from a client push). Handles re-push."""
        session_id = payload["id"]

        with self._session() as session:
            # Clear existing data for re-push
            session.execute(delete(Message).where(Message.session_id == session_id))
            session.execute(delete(Enrichment).where(Enrichment.session_id == session_id))
            session.execute(delete(Annotation).where(Annotation.session_id == session_id))
            session.execute(
                delete(Edge).where(Edge.source_type == "session", Edge.source_id == session_id)
            )
            if self._dialect == "sqlite":
                session.execute(
                    text("DELETE FROM sessions_fts WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            elif self._dialect == "postgresql":
                session.execute(
                    text("DELETE FROM sessions_fts_pg WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            session.execute(delete(SessionModel).where(SessionModel.id == session_id))

            # Insert session
            session.add(
                SessionModel(
                    id=session_id,
                    source=payload.get("source", ""),
                    project_path=payload.get("project_path"),
                    author=payload.get("author"),
                    started_at=payload.get("started_at"),
                    ended_at=payload.get("ended_at"),
                    message_count=payload.get("message_count", 0),
                    summary=payload.get("summary"),
                )
            )

            for msg in payload.get("messages", []):
                session.add(
                    Message(
                        session_id=session_id,
                        ordinal=msg.get("ordinal", 0),
                        role=msg.get("role", "human"),
                        content=msg.get("content"),
                        tool_name=msg.get("tool_name"),
                        timestamp=msg.get("timestamp"),
                    )
                )

            for e in payload.get("enrichments", []):
                session.add(
                    Enrichment(
                        session_id=session_id,
                        source=e.get("source", ""),
                        key=e.get("key", ""),
                        value=e.get("value"),
                    )
                )

            for a in payload.get("annotations", []):
                session.add(
                    Annotation(
                        session_id=session_id,
                        type=a.get("type", "tag"),
                        value=a.get("value", ""),
                        author=a.get("author"),
                    )
                )

            for edge in payload.get("edges", []):
                session.add(
                    Edge(
                        source_type=edge.get("source_type", ""),
                        source_id=edge.get("source_id", ""),
                        target_type=edge.get("target_type", ""),
                        target_id=edge.get("target_id", ""),
                        relationship_=edge.get("relationship", ""),
                    )
                )

            # Flush ORM inserts so FK constraints are satisfied for FTS
            session.flush()

            # FTS index
            fts_parts = [
                msg.get("content", "") for msg in payload.get("messages", []) if msg.get("content")
            ]
            if fts_parts:
                fts_content = "\n".join(fts_parts)
                if self._dialect == "sqlite":
                    session.execute(
                        text(
                            "INSERT INTO sessions_fts (session_id, content) VALUES (:sid, :content)"
                        ),
                        {"sid": session_id, "content": fts_content},
                    )
                elif self._dialect == "postgresql":
                    session.execute(
                        text(
                            "INSERT INTO sessions_fts_pg (session_id, content) "
                            "VALUES (:sid, :content) "
                            "ON CONFLICT (session_id) DO UPDATE SET content = EXCLUDED.content"
                        ),
                        {"sid": session_id, "content": fts_content},
                    )

            session.commit()

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


def _session_to_dict(s: SessionModel) -> dict[str, Any]:
    """Convert a Session ORM object to a plain dict."""
    return {
        "id": s.id,
        "source": s.source,
        "project_path": s.project_path,
        "author": s.author,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "message_count": s.message_count,
        "summary": s.summary,
    }
