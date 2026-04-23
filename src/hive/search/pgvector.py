"""PostgreSQL pgvector search backend — semantic search via pgvector extension."""

from __future__ import annotations

import json
import logging
from typing import Any

from hive.search.base import SearchBackend
from hive.search.helpers import session_uuid

logger = logging.getLogger(__name__)

_DEFAULT_DIM = 384


class PgvectorBackend(SearchBackend):
    """Semantic search using PostgreSQL with the pgvector extension and sentence-transformers."""

    def __init__(
        self,
        dsn: str,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.dsn = dsn
        self.model_name = model_name
        self._model = None
        self._dim: int | None = None
        self._db_initialized = False

    def _ensure_db(self) -> None:
        """Create search tables if they don't exist."""
        if self._db_initialized:
            return

        dim = self._get_dim()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_documents (
                uuid TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                date TEXT,
                metadata JSONB NOT NULL,
                body TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_docs_session ON search_documents(session_id)"
        )
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS search_chunks (
                id SERIAL PRIMARY KEY,
                doc_uuid TEXT NOT NULL REFERENCES search_documents(uuid) ON DELETE CASCADE,
                chunk_idx INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedded BOOLEAN NOT NULL DEFAULT FALSE,
                embedding vector({dim})
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_search_chunks_doc ON search_chunks(doc_uuid)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_chunks_pending "
            "ON search_chunks(embedded) WHERE embedded = FALSE"
        )
        conn.commit()
        cur.close()
        conn.close()
        self._db_initialized = True

    def _conn(self):
        """Open a PostgreSQL connection with pgvector registered."""
        import psycopg2

        conn = psycopg2.connect(self.dsn)
        try:
            from pgvector.psycopg2 import register_vector

            register_vector(conn)
        except ImportError:
            pass
        return conn

    def _get_dim(self) -> int:
        """Return the embedding dimension for the configured model."""
        if self._dim is not None:
            return self._dim
        known = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
            "all-distilroberta-v1": 768,
        }
        self._dim = known.get(self.model_name, _DEFAULT_DIM)
        return self._dim

    def _get_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)
        self._dim = self._model.get_embedding_dimension()
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]

    def is_available(self) -> bool:
        """Check if PostgreSQL is reachable and pgvector extension exists."""
        try:
            import psycopg2  # noqa: F401
            import sentence_transformers  # noqa: F401

            conn = self._conn()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            available = cur.fetchone() is not None
            cur.close()
            conn.close()
            return available
        except Exception:
            return False

    def add_document(
        self,
        session_id: str,
        date: str | None,
        metadata: dict[str, Any],
        body: str,
        chunk_lengths: list[int],
    ) -> None:
        """Store document and chunks (embedding deferred to trigger_index)."""
        self._ensure_db()
        doc_uuid = session_uuid(session_id)
        conn = self._conn()
        cur = conn.cursor()

        # Upsert document
        cur.execute(
            """INSERT INTO search_documents (uuid, session_id, date, metadata, body)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (uuid) DO UPDATE
               SET session_id = EXCLUDED.session_id,
                   date = EXCLUDED.date,
                   metadata = EXCLUDED.metadata,
                   body = EXCLUDED.body""",
            (doc_uuid, session_id, date, json.dumps(metadata), body),
        )

        # Remove old chunks for this document
        cur.execute("DELETE FROM search_chunks WHERE doc_uuid = %s", (doc_uuid,))

        # Split body by chunk_lengths and insert chunks
        offset = 0
        for idx, length in enumerate(chunk_lengths):
            chunk_text = body[offset : offset + length].strip()
            if chunk_text:
                cur.execute(
                    """INSERT INTO search_chunks (doc_uuid, chunk_idx, text, embedded)
                       VALUES (%s, %s, %s, FALSE)""",
                    (doc_uuid, idx, chunk_text),
                )
            offset += length

        # If no chunk_lengths provided, store body as a single chunk
        if not chunk_lengths and body.strip():
            cur.execute(
                """INSERT INTO search_chunks (doc_uuid, chunk_idx, text, embedded)
                   VALUES (%s, %s, %s, FALSE)""",
                (doc_uuid, 0, body.strip()),
            )

        conn.commit()
        cur.close()
        conn.close()

    def remove_document(self, session_id: str) -> None:
        """Remove a document and its chunks from the index."""
        self._ensure_db()
        doc_uuid = session_uuid(session_id)
        conn = self._conn()
        cur = conn.cursor()
        # CASCADE handles chunks
        cur.execute("DELETE FROM search_documents WHERE uuid = %s", (doc_uuid,))
        conn.commit()
        cur.close()
        conn.close()

    def search(
        self,
        query: str,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Embed query and search via KNN using pgvector cosine distance."""
        self._ensure_db()
        query_embedding = self._embed([query])[0]

        conn = self._conn()
        cur = conn.cursor()

        # KNN search — fetch more than limit to allow for metadata filtering
        fetch_limit = limit * 5
        cur.execute(
            """
            SELECT c.id AS chunk_id, c.doc_uuid, c.chunk_idx, c.text,
                   d.metadata, d.date,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM search_chunks c
            JOIN search_documents d ON c.doc_uuid = d.uuid
            WHERE c.embedded = TRUE
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, fetch_limit),
        )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return []

        # Apply metadata filters and deduplicate by session
        results = []
        seen_sessions: set[str] = set()
        for _chunk_id, _doc_uuid, chunk_idx, chunk_text, metadata, date, score in rows:
            meta = metadata if isinstance(metadata, dict) else json.loads(metadata)
            if project and project.lower() not in (meta.get("project_path") or "").lower():
                continue
            if author and meta.get("author") != author:
                continue
            if since and (meta.get("started_at") or "") < since:
                continue
            if until and (meta.get("started_at") or "") > until:
                continue

            sid = meta.get("session_id", "")
            if sid in seen_sessions:
                continue
            seen_sessions.add(sid)

            results.append(
                {
                    "score": max(0.0, float(score)),
                    "metadata": meta,
                    "body": chunk_text,
                    "sub_idx": chunk_idx,
                    "date": date or "",
                }
            )

            if len(results) >= limit:
                break

        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        """Embed all pending chunks and update their embedding column."""
        self._ensure_db()
        conn = self._conn()
        cur = conn.cursor()

        sql = "SELECT id, text FROM search_chunks WHERE embedded = FALSE"
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        pending = cur.fetchall()

        if not pending:
            cur.close()
            conn.close()
            return {"embedded": 0}

        chunk_ids = [row[0] for row in pending]
        texts = [row[1] for row in pending]

        # Embed in batches
        batch_size = 64
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._embed(batch))

        # Update embeddings
        for cid, emb in zip(chunk_ids, all_embeddings, strict=True):
            cur.execute(
                "UPDATE search_chunks SET embedding = %s::vector, embedded = TRUE WHERE id = %s",
                (emb, cid),
            )

        conn.commit()
        cur.close()
        conn.close()
        return {"embedded": len(chunk_ids)}
