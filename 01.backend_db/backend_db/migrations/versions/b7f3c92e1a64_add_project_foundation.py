"""add project foundation

Revision ID: b7f3c92e1a64
Revises: a006ca44c863
Create Date: 2026-09-04 13:20:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "b7f3c92e1a64"
down_revision: str | Sequence[str] | None = "a006ca44c863"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增项目档案，并为 V1 存量数据预留可空项目归属。"""

    op.create_table(
        "project",
        sa.Column(
            "project_code",
            sa.String(length=64),
            nullable=False,
            comment="项目稳定业务编码",
        ),
        sa.Column(
            "project_name",
            sa.String(length=128),
            nullable=False,
            comment="项目名称",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="是否启用",
        ),
        sa.Column(
            "remark",
            sa.String(length=500),
            nullable=True,
            comment="备注",
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
        sa.UniqueConstraint(
            "project_code",
            name=op.f("uq_project_project_code"),
        ),
    )

    for table_name in ("beam_type", "yard_area", "beam"):
        op.add_column(
            table_name,
            sa.Column(
                "project_id",
                sa.BigInteger(),
                nullable=True,
                comment="所属项目ID；V2过渡期允许为空",
            ),
        )
        op.create_index(
            op.f(f"ix_{table_name}_project_id"),
            table_name,
            ["project_id"],
            unique=False,
        )
        op.create_foreign_key(
            op.f(f"fk_{table_name}_project_id_project"),
            table_name,
            "project",
            ["project_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """移除项目归属，不删除任何 V1 业务记录。"""

    for table_name in ("beam", "yard_area", "beam_type"):
        op.drop_constraint(
            op.f(f"fk_{table_name}_project_id_project"),
            table_name,
            type_="foreignkey",
        )
        op.drop_index(
            op.f(f"ix_{table_name}_project_id"),
            table_name=table_name,
        )
        op.drop_column(table_name, "project_id")

    op.drop_table("project")
