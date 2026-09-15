"""add beam process execution

Revision ID: d4a6f8b0c217
Revises: c8f2d4e6a013
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "d4a6f8b0c217"
down_revision: str | Sequence[str] | None = "c8f2d4e6a013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_process_execution",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("execution_code", sa.String(64), nullable=False),
        sa.Column("beam_id", sa.BigInteger(), nullable=False),
        sa.Column("process_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("result_code", sa.String(32), nullable=False),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_record_id", sa.String(128), nullable=True),
        sa.Column("supersedes_execution_id", sa.BigInteger(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("is_voided", sa.Boolean(), nullable=False),
        sa.Column("voided_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("voided_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("voided_by_name", sa.String(128), nullable=True),
        sa.Column("void_reason", sa.String(500), nullable=True),
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
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        sa.CheckConstraint(
            "finished_at >= started_at",
            name="ck_beam_process_execution_time_order",
        ),
        sa.CheckConstraint(
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_process_execution_void_fields",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["beam_id"], ["beam.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["process_definition_id"],
            ["process_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_execution_id"],
            ["beam_process_execution.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_code"),
        sa.UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_process_execution_source_external",
        ),
        sa.UniqueConstraint(
            "supersedes_execution_id",
            name="uq_beam_process_execution_supersedes",
        ),
    )
    op.create_index(
        "ix_beam_process_execution_project_finished_id",
        "beam_process_execution",
        ["project_id", "finished_at", "id"],
    )
    op.create_index(
        "ix_beam_process_execution_beam_finished_id",
        "beam_process_execution",
        ["beam_id", "finished_at", "id"],
    )
    op.create_index(
        "ix_beam_process_execution_process_finished_id",
        "beam_process_execution",
        ["process_definition_id", "finished_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("beam_process_execution")
