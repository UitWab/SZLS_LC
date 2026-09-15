"""add beam lifecycle event

Revision ID: b7e1c3d5f902
Revises: a4d7e9f2c105
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "b7e1c3d5f902"
down_revision: str | Sequence[str] | None = "a4d7e9f2c105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_lifecycle_event",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("beam_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("status_before", sa.String(32), nullable=True),
        sa.Column("status_after", sa.String(32), nullable=True),
        sa.Column("source_position_id", sa.BigInteger(), nullable=True),
        sa.Column("target_position_id", sa.BigInteger(), nullable=True),
        sa.Column("work_order_id", sa.BigInteger(), nullable=True),
        sa.Column("occurred_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            comment="创建时间（UTC）",
        ),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["beam_id"], ["beam.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_position_id"],
            ["beam_position.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_position_id"],
            ["beam_position.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["beam_position_work_order.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_beam_event_project_occurred_id",
        "beam_lifecycle_event",
        ["project_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_beam_event_beam_occurred_id",
        "beam_lifecycle_event",
        ["beam_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("beam_lifecycle_event")
