"""Add PostgreSQL full-text search table (tsvector equivalent of FTS5).

Revision ID: 002
Revises: 001
Create Date: 2026-04-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions_fts_pg (
                session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                search_vector TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('english', content)
                ) STORED
            )
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_fts_pg_vector
            ON sessions_fts_pg USING GIN (search_vector)
            """
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TABLE IF EXISTS sessions_fts_pg")
