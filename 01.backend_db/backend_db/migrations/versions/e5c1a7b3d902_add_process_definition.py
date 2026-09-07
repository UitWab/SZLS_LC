"""add process definition

Revision ID: e5c1a7b3d902
Revises: d2a8f41c6e90
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "e5c1a7b3d902"
down_revision: str | Sequence[str] | None = "d2a8f41c6e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "process_definition",
        sa.Column("project_id", sa.BigInteger(), nullable=True,
                  comment="所属项目ID；为空表示平台通用工序"),
        sa.Column("process_code", sa.String(64), nullable=False,
                  comment="工序稳定业务编码"),
        sa.Column("process_name", sa.String(128), nullable=False,
                  comment="工序名称"),
        sa.Column("sort_order", sa.Integer(), nullable=False,
                  comment="显示排序"),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  comment="是否启用"),
        sa.Column("remark", sa.String(500), nullable=True, comment="备注"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False,
                  comment="技术主键"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False,
                  comment="创建时间（UTC）"),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False,
                  comment="更新时间（UTC）"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("process_code"),
    )
    op.create_index(
        op.f("ix_process_definition_project_id"),
        "process_definition",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_table("process_definition")
