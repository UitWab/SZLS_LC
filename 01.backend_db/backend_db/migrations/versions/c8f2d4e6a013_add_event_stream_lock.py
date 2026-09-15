"""add event stream lock

Revision ID: c8f2d4e6a013
Revises: b7e1c3d5f902
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8f2d4e6a013"
down_revision: str | Sequence[str] | None = "b7e1c3d5f902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_lifecycle_event_stream_lock",
        sa.Column("scope_key", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("scope_key"),
    )
    op.create_index(
        "ix_beam_event_project_id",
        "beam_lifecycle_event",
        ["project_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_beam_event_project_id",
        table_name="beam_lifecycle_event",
    )
    op.drop_table("beam_lifecycle_event_stream_lock")
