"""add beam quality inspection

Revision ID: e7b9c1d3f605
Revises: d4a6f8b0c217
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "e7b9c1d3f605"
down_revision: str | Sequence[str] | None = "d4a6f8b0c217"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_quality_inspection",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("inspection_code", sa.String(64), nullable=False),
        sa.Column("beam_id", sa.BigInteger(), nullable=False),
        sa.Column("process_definition_id", sa.BigInteger(), nullable=True),
        sa.Column("process_execution_id", sa.BigInteger(), nullable=True),
        sa.Column("previous_inspection_id", sa.BigInteger(), nullable=True),
        sa.Column("inspection_type_code", sa.String(64), nullable=False),
        sa.Column("result_code", sa.String(32), nullable=False),
        sa.Column("inspected_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_record_id", sa.String(128), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
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
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_quality_inspection_void_fields",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["beam_id"], ["beam.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["process_definition_id"],
            ["process_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["process_execution_id"],
            ["beam_process_execution.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_inspection_id"],
            ["beam_quality_inspection.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_code"),
        sa.UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_quality_inspection_source_external",
        ),
    )
    op.create_index(
        "ix_beam_quality_inspection_project_inspected_id",
        "beam_quality_inspection",
        ["project_id", "inspected_at", "id"],
    )
    op.create_index(
        "ix_beam_quality_inspection_beam_inspected_id",
        "beam_quality_inspection",
        ["beam_id", "inspected_at", "id"],
    )
    op.create_index(
        "ix_beam_quality_inspection_process_inspected_id",
        "beam_quality_inspection",
        ["process_definition_id", "inspected_at", "id"],
    )
    op.create_index(
        "ix_beam_quality_inspection_process_execution_id",
        "beam_quality_inspection",
        ["process_execution_id"],
    )
    op.create_index(
        "ix_beam_quality_inspection_previous_inspection_id",
        "beam_quality_inspection",
        ["previous_inspection_id"],
    )

    op.create_table(
        "beam_quality_inspection_item",
        sa.Column("inspection_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "item_code",
            sa.String(64, collation="utf8mb4_bin"),
            nullable=False,
        ),
        sa.Column("item_name", sa.String(128), nullable=False),
        sa.Column("requirement_text", sa.String(500), nullable=True),
        sa.Column("observed_value", sa.String(128), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("result_code", sa.String(32), nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["beam_quality_inspection.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "inspection_id",
            "item_code",
            name="uq_beam_quality_inspection_item_code",
        ),
    )
    op.create_index(
        "ix_beam_quality_inspection_item_inspection_id",
        "beam_quality_inspection_item",
        ["inspection_id"],
    )


def downgrade() -> None:
    op.drop_table("beam_quality_inspection_item")
    op.drop_table("beam_quality_inspection")
