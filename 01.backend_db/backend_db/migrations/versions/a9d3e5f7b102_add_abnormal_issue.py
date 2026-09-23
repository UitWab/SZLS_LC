"""add abnormal issue

Revision ID: a9d3e5f7b102
Revises: f8c2d4e6a709
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "a9d3e5f7b102"
down_revision: str | Sequence[str] | None = "f8c2d4e6a709"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "abnormal_issue",
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_code", sa.String(64), nullable=False),
        sa.Column("beam_id", sa.BigInteger(), nullable=True),
        sa.Column("device_code", sa.String(64), nullable=True),
        sa.Column("category_code", sa.String(32), nullable=False),
        sa.Column("issue_type_code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("occurred_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("reported_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reported_by_name", sa.String(128), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_record_id", sa.String(128), nullable=True),
        sa.Column("processing_started_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("processing_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("processing_by_name", sa.String(128), nullable=True),
        sa.Column("resolved_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("resolved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_by_name", sa.String(128), nullable=True),
        sa.Column("resolution_summary", sa.String(500), nullable=True),
        sa.Column("closed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("closed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("closed_by_name", sa.String(128), nullable=True),
        sa.Column("close_note", sa.String(500), nullable=True),
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
            "(status = 'OPEN' "
            "AND processing_started_at IS NULL "
            "AND processing_by_user_id IS NULL "
            "AND processing_by_name IS NULL "
            "AND resolved_at IS NULL "
            "AND resolved_by_user_id IS NULL "
            "AND resolved_by_name IS NULL "
            "AND resolution_summary IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'IN_PROGRESS' "
            "AND processing_started_at IS NOT NULL "
            "AND (processing_by_user_id IS NOT NULL OR processing_by_name IS NOT NULL) "
            "AND resolved_at IS NULL "
            "AND resolved_by_user_id IS NULL "
            "AND resolved_by_name IS NULL "
            "AND resolution_summary IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'RESOLVED' "
            "AND resolved_at IS NOT NULL "
            "AND (resolved_by_user_id IS NOT NULL OR resolved_by_name IS NOT NULL) "
            "AND resolution_summary IS NOT NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'CLOSED' "
            "AND resolved_at IS NOT NULL "
            "AND (resolved_by_user_id IS NOT NULL OR resolved_by_name IS NOT NULL) "
            "AND resolution_summary IS NOT NULL "
            "AND closed_at IS NOT NULL "
            "AND (closed_by_user_id IS NOT NULL OR closed_by_name IS NOT NULL))",
            name="ck_abnormal_issue_status_fields",
        ),
        sa.CheckConstraint(
            "(processing_started_at IS NULL "
            "AND processing_by_user_id IS NULL "
            "AND processing_by_name IS NULL) OR "
            "(processing_started_at IS NOT NULL "
            "AND (processing_by_user_id IS NOT NULL OR processing_by_name IS NOT NULL))",
            name="ck_abnormal_issue_processing_actor",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["beam_id"], ["beam.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reported_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["processing_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_code"),
        sa.UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_abnormal_issue_source_external",
        ),
    )
    op.create_index(
        "ix_abnormal_issue_project_occurred_id",
        "abnormal_issue",
        ["project_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_abnormal_issue_project_status_occurred_id",
        "abnormal_issue",
        ["project_id", "status", "occurred_at", "id"],
    )
    op.create_index(
        "ix_abnormal_issue_project_category_status_occurred_id",
        "abnormal_issue",
        ["project_id", "category_code", "status", "occurred_at", "id"],
    )
    op.create_index(
        "ix_abnormal_issue_beam_occurred_id",
        "abnormal_issue",
        ["beam_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_abnormal_issue_project_device_occurred_id",
        "abnormal_issue",
        ["project_id", "device_code", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("abnormal_issue")
