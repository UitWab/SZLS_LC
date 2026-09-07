"""add identity access foundation

Revision ID: c9d4e6f1a2b8
Revises: b7f3c92e1a64
Create Date: 2026-09-04 13:45:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "c9d4e6f1a2b8"
down_revision: str | Sequence[str] | None = "b7f3c92e1a64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "app_user",
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("username", name=op.f("uq_app_user_username")),
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "auth_role",
        sa.Column("role_code", sa.String(64), nullable=False),
        sa.Column("role_name", sa.String(128), nullable=False),
        sa.Column("role_scope", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_role")),
        sa.UniqueConstraint("role_code", name=op.f("uq_auth_role_role_code")),
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "auth_permission",
        sa.Column("permission_code", sa.String(128), nullable=False),
        sa.Column("permission_name", sa.String(128), nullable=False),
        sa.Column("module_code", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="技术主键",
        ),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_permission")),
        sa.UniqueConstraint(
            "permission_code",
            name=op.f("uq_auth_permission_permission_code"),
        ),
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "user_credential",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "password_changed_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_user_credential_user_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_credential")),
    )

    op.create_table(
        "auth_role_permission",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["auth_permission.id"],
            name=op.f(
                "fk_auth_role_permission_permission_id_auth_permission"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["auth_role.id"],
            name=op.f("fk_auth_role_permission_role_id_auth_role"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
            name=op.f("pk_auth_role_permission"),
        ),
    )


def downgrade() -> None:
    op.drop_table("auth_role_permission")
    op.drop_table("user_credential")
    op.drop_table("auth_permission")
    op.drop_table("auth_role")
    op.drop_table("app_user")
