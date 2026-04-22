"""Baseline schema — matches the v0.1.0 hive database.

Revision ID: 001
Revises: None
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("project_path", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("ended_at", sa.String(), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_project", "sessions", ["project_path"])
    op.create_index("idx_sessions_started", "sessions", ["started_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("timestamp", sa.String(), nullable=True),
        sa.CheckConstraint("role IN ('human', 'assistant', 'tool')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_messages_session", "messages", ["session_id"])

    op.create_table(
        "enrichments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("enriched_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_enrichments_session", "enrichments", ["session_id"])
    op.create_index("idx_enrichments_key", "enrichments", ["session_id", "key"])

    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("type IN ('tag', 'comment', 'rating')", name="ck_annotations_type"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_annotations_session", "annotations", ["session_id"])

    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("relationship", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_edges_source", "edges", ["source_type", "source_id"])
    op.create_index("idx_edges_target", "edges", ["target_type", "target_id"])

    # FTS5 is SQLite-specific — guarded by dialect check
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
                session_id,
                content,
                tokenize='porter'
            )
            """
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TABLE IF EXISTS sessions_fts")

    op.drop_table("edges")
    op.drop_table("annotations")
    op.drop_table("enrichments")
    op.drop_table("messages")
    op.drop_table("sessions")
