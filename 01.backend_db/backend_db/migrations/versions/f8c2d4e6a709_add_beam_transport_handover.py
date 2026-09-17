"""add beam transport handover

Revision ID: f8c2d4e6a709
Revises: e7b9c1d3f605
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "f8c2d4e6a709"
down_revision: str | Sequence[str] | None = "e7b9c1d3f605"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_transport_handover",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("handover_code", sa.String(64), nullable=False),
        sa.Column("beam_id", sa.BigInteger(), nullable=False),
        sa.Column("handover_type", sa.String(32), nullable=False),
        sa.Column("result_code", sa.String(32), nullable=False),
        sa.Column("from_location", sa.String(255), nullable=True),
        sa.Column("to_location", sa.String(255), nullable=True),
        sa.Column("carrier_name", sa.String(128), nullable=True),
        sa.Column("vehicle_no", sa.String(64), nullable=True),
        sa.Column("sender_name", sa.String(128), nullable=True),
        sa.Column("receiver_name", sa.String(128), nullable=True),
        sa.Column("occurred_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_record_id", sa.String(128), nullable=True),
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
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_transport_handover_void_fields",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["beam_id"], ["beam.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handover_code"),
        sa.UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_transport_handover_source_external",
        ),
    )
    op.create_index(
        "ix_beam_transport_handover_project_occurred_id",
        "beam_transport_handover",
        ["project_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_beam_transport_handover_beam_occurred_id",
        "beam_transport_handover",
        ["beam_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("beam_transport_handover")
