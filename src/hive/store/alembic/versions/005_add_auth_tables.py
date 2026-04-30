"""Add auth tables: users, refresh_tokens; add user_id to sessions and annotations.

Revision ID: 005
Revises: 004
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("oidc_subject", sa.String(), nullable=True),
        sa.Column("oidc_issuer", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_login_at", sa.String(), nullable=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revoked_at", sa.String(), nullable=True),
    )
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"])

    op.add_column("sessions", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("annotations", sa.Column("user_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("annotations", "user_id")
    op.drop_column("sessions", "user_id")
    op.drop_index("idx_refresh_tokens_hash", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
