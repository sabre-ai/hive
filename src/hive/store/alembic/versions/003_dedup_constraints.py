"""Add deduplication constraints to annotations and edges tables.

Revision ID: 003
Revises: 002
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Deduplicate existing rows before adding constraints ---

    # Keep only the first (lowest id) row for each (session_id, type, value) in annotations
    op.execute(
        """
        DELETE FROM annotations WHERE id NOT IN (
            SELECT MIN(id) FROM annotations GROUP BY session_id, type, value
        )
        """
    )

    # Keep only the first row for each (source_type, source_id, target_type, target_id, relationship)
    op.execute(
        """
        DELETE FROM edges WHERE id NOT IN (
            SELECT MIN(id) FROM edges
            GROUP BY source_type, source_id, target_type, target_id, relationship
        )
        """
    )

    # --- Add unique constraints ---

    with op.batch_alter_table("annotations") as batch_op:
        batch_op.create_unique_constraint("uq_annotations_dedup", ["session_id", "type", "value"])

    with op.batch_alter_table("edges") as batch_op:
        batch_op.create_unique_constraint(
            "uq_edges_dedup",
            ["source_type", "source_id", "target_type", "target_id", "relationship"],
        )


def downgrade() -> None:
    with op.batch_alter_table("edges") as batch_op:
        batch_op.drop_constraint("uq_edges_dedup", type_="unique")

    with op.batch_alter_table("annotations") as batch_op:
        batch_op.drop_constraint("uq_annotations_dedup", type_="unique")
