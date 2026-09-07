"""add operation audit log

Revision ID: f8a2d4c6b901
Revises: e5c1a7b3d902
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "f8a2d4c6b901"
down_revision: str | Sequence[str] | None = "e5c1a7b3d902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_audit_log",
        sa.Column("project_id", sa.BigInteger(), nullable=True,
                  comment="所属项目ID；系统级操作允许为空"),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True,
                  comment="操作用户ID；未登录或系统操作允许为空"),
        sa.Column("actor_name", sa.String(128), nullable=True,
                  comment="操作人显示名称或标识快照"),
        sa.Column("action_code", sa.String(64), nullable=False,
                  comment="由 B 定义的稳定操作代码"),
        sa.Column("resource_type", sa.String(64), nullable=False,
                  comment="被操作资源类型代码"),
        sa.Column("resource_code", sa.String(128), nullable=True,
                  comment="被操作资源的稳定业务编码"),
        sa.Column("result_code", sa.String(32), nullable=False,
                  comment="由 B 定义的操作结果代码"),
        sa.Column("request_id", sa.String(128), nullable=True,
                  comment="B 层请求追踪标识"),
        sa.Column("source", sa.String(32), nullable=True,
                  comment="操作来源代码"),
        sa.Column("summary", sa.String(500), nullable=True,
                  comment="不含敏感数据的操作摘要"),
        sa.Column("occurred_at", mysql.DATETIME(fsp=6), nullable=False,
                  comment="业务发生时间（UTC）"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False,
                  comment="技术主键"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False,
                  comment="入库时间（UTC）"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_audit_log_occurred_id",
        "operation_audit_log", ["occurred_at", "id"]
    )
    op.create_index(
        "ix_operation_audit_log_project_occurred_id",
        "operation_audit_log", ["project_id", "occurred_at", "id"]
    )
    op.create_index(
        "ix_operation_audit_log_actor_occurred_id",
        "operation_audit_log", ["actor_user_id", "occurred_at", "id"]
    )
    op.create_index(
        "ix_operation_audit_log_resource_occurred",
        "operation_audit_log", ["resource_type", "resource_code", "occurred_at"]
    )
    op.create_index(
        "ix_operation_audit_log_request_id",
        "operation_audit_log", ["request_id"]
    )


def downgrade() -> None:
    op.drop_table("operation_audit_log")
