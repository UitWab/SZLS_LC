"""add beam position work order

Revision ID: a4d7e9f2c105
Revises: f8a2d4c6b901
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "a4d7e9f2c105"
down_revision: str | Sequence[str] | None = "f8a2d4c6b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_position_work_order",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("work_order_code", sa.String(64), nullable=False),
        sa.Column("order_type", sa.String(32), nullable=False),
        sa.Column("beam_id", sa.BigInteger(), nullable=False),
        sa.Column("source_position_id", sa.BigInteger(), nullable=True),
        sa.Column("target_position_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("planned_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            comment="创建时间（UTC）",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            comment="更新时间（UTC）",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_order_code"),
    )
    op.create_index(
        "ix_bpw_order_project_status_id",
        "beam_position_work_order",
        ["project_id", "status", "id"],
    )
    op.create_index(
        "ix_bpw_order_beam_status",
        "beam_position_work_order",
        ["beam_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("beam_position_work_order")
