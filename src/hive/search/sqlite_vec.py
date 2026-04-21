"""SQLite-vec search backend — in-process vector search, no external server."""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any

from hive.search.base import SearchBackend
from hive.search.helpers import session_uuid

logger = logging.getLogger(__name__)

# Embedding dimension for all-MiniLM-L6-v2 (default model)
_DEFAULT_DIM = 384


def _serialize_f32(vec: list[float]) -> bytes:
    """Serialize a float32 vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


class SqliteVecBackend(SearchBackend):
    """In-process semantic search using sqlite-vec and sentence-transformers."""

    def __init__(
        self,
        db_path: Path | str = "search_vec.db",
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.db_path = Path(db_path)
        self.model_name = model_name
        self._model = None
        self._dim: int | None = None
        self._db_initialized = False

    def _ensure_db(self) -> None:
        """Create tables if they don't exist."""
        if self._db_initialized:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                uuid TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                date TEXT,
                metadata TEXT NOT NULL,
                body TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_uuid TEXT NOT NULL,
                chunk_idx INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedded INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (doc_uuid) REFERENCES documents(uuid) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_uuid);
            CREATE INDEX IF NOT EXISTS idx_chunks_pending ON chunks(embedded) WHERE embedded = 0;
        """)
        conn.commit()

        # Create the vec0 virtual table — requires sqlite-vec extension
        dim = self._get_dim()
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks
                USING vec0(embedding float[{dim}], chunk_id integer)
            """)
            conn.commit()
        except Exception:
            logger.debug("Failed to create vec_chunks table (sqlite-vec may not be available)")

        conn.close()
        self._db_initialized = True

    def _conn(self) -> sqlite3.Connection:
        """Open a connection with sqlite-vec loaded."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            import sqlite_vec

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except (ImportError, Exception):
            pass
        return conn

    def _get_dim(self) -> int:
        """Return the embedding dimension for the configured model."""
        if self._dim is not None:
            return self._dim
        # Known dimensions for common models
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
        """Check if sqlite-vec and sentence-transformers are importable."""
        try:
            import sentence_transformers  # noqa: F401
            import sqlite_vec  # noqa: F401

            return True
        except ImportError:
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

        # Upsert document
        conn.execute(
            """INSERT OR REPLACE INTO documents (uuid, session_id, date, metadata, body)
               VALUES (?, ?, ?, ?, ?)""",
            (doc_uuid, session_id, date, json.dumps(metadata), body),
        )

        # Remove old chunks for this document
        conn.execute("DELETE FROM chunks WHERE doc_uuid = ?", (doc_uuid,))

        # Split body by chunk_lengths and insert chunks
        offset = 0
        for idx, length in enumerate(chunk_lengths):
            text = body[offset : offset + length].strip()
            if text:
                conn.execute(
                    """INSERT INTO chunks (doc_uuid, chunk_idx, text, embedded)
                       VALUES (?, ?, ?, 0)""",
                    (doc_uuid, idx, text),
                )
            offset += length

        # If no chunk_lengths provided, store body as a single chunk
        if not chunk_lengths and body.strip():
            conn.execute(
                """INSERT INTO chunks (doc_uuid, chunk_idx, text, embedded)
                   VALUES (?, ?, ?, 0)""",
                (doc_uuid, 0, body.strip()),
            )

        conn.commit()
        conn.close()

    def remove_document(self, session_id: str) -> None:
        """Remove a document and its chunks from the index."""
        self._ensure_db()
        doc_uuid = session_uuid(session_id)
        conn = self._conn()

        # Remove from vec index
        try:
            chunk_ids = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM chunks WHERE doc_uuid = ?", (doc_uuid,)
                ).fetchall()
            ]
            for cid in chunk_ids:
                conn.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", (cid,))
        except Exception:
            pass

        # CASCADE will handle chunks via foreign key
        conn.execute("DELETE FROM chunks WHERE doc_uuid = ?", (doc_uuid,))
        conn.execute("DELETE FROM documents WHERE uuid = ?", (doc_uuid,))
        conn.commit()
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
        """Embed query and search via KNN in sqlite-vec."""
        self._ensure_db()
        query_embedding = self._embed([query])[0]
        query_bytes = _serialize_f32(query_embedding)

        conn = self._conn()

        # KNN search via vec0 — fetch more than limit to allow for filtering
        fetch_limit = limit * 5
        try:
            rows = conn.execute(
                """
                SELECT v.chunk_id, v.distance
                FROM vec_chunks v
                WHERE v.embedding MATCH ?
                ORDER BY v.distance
                LIMIT ?
                """,
                (query_bytes, fetch_limit),
            ).fetchall()
        except Exception:
            conn.close()
            return []

        if not rows:
            conn.close()
            return []

        # Join with chunks and documents
        chunk_ids = [row[0] for row in rows]
        distances = {row[0]: row[1] for row in rows}

        placeholders = ",".join("?" for _ in chunk_ids)
        joined = conn.execute(
            f"""
            SELECT c.id AS chunk_id, c.doc_uuid, c.chunk_idx, c.text,
                   d.metadata, d.date
            FROM chunks c
            JOIN documents d ON c.doc_uuid = d.uuid
            WHERE c.id IN ({placeholders})
            """,
            chunk_ids,
        ).fetchall()
        conn.close()

        # Apply metadata filters and build results
        results = []
        seen_sessions: set[str] = set()
        for row in joined:
            meta = json.loads(row["metadata"])
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

            distance = distances.get(row["chunk_id"], 1.0)
            # Convert distance to similarity score (1 - cosine_distance)
            score = max(0.0, 1.0 - distance)

            results.append(
                {
                    "score": score,
                    "metadata": meta,
                    "body": row["text"],
                    "sub_idx": row["chunk_idx"],
                    "date": row["date"] or "",
                }
            )

            if len(results) >= limit:
                break

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def trigger_index(self, limit: int | None = None) -> dict[str, Any]:
        """Embed all pending chunks and insert into the vec0 index."""
        self._ensure_db()
        conn = self._conn()

        query = "SELECT id, text FROM chunks WHERE embedded = 0"
        if limit:
            query += f" LIMIT {int(limit)}"
        pending = conn.execute(query).fetchall()

        if not pending:
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

        # Insert into vec0 and mark as embedded
        for cid, emb in zip(chunk_ids, all_embeddings, strict=True):
            emb_bytes = _serialize_f32(emb)
            conn.execute(
                "INSERT OR REPLACE INTO vec_chunks (embedding, chunk_id) VALUES (?, ?)",
                (emb_bytes, cid),
            )
            conn.execute("UPDATE chunks SET embedded = 1 WHERE id = ?", (cid,))

        conn.commit()
        conn.close()
        return {"embedded": len(chunk_ids)}
