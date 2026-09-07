"""add project membership

Revision ID: d2a8f41c6e90
Revises: c9d4e6f1a2b8
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "d2a8f41c6e90"
down_revision: str | Sequence[str] | None = "c9d4e6f1a2b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_user_role",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["auth_role.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "project_member",
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="技术主键"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, comment="创建时间（UTC）"),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, comment="更新时间（UTC）"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )
    op.create_index(op.f("ix_project_member_project_id"), "project_member", ["project_id"])
    op.create_index(op.f("ix_project_member_user_id"), "project_member", ["user_id"])
    op.create_table(
        "project_member_role",
        sa.Column("project_member_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["project_member_id"], ["project_member.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["auth_role.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_member_id", "role_id"),
    )


def downgrade() -> None:
    op.drop_table("project_member_role")
    op.drop_table("project_member")
    op.drop_table("auth_user_role")
