"""Add projects table and project_id column to sessions.

Revision ID: 004
Revises: 003
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(), nullable=True),
    )

    op.add_column("sessions", sa.Column("project_id", sa.String(), nullable=True))
    op.create_index("idx_sessions_project_id", "sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("idx_sessions_project_id", table_name="sessions")
    op.drop_column("sessions", "project_id")
    op.drop_table("projects")
