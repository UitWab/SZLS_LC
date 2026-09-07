from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, utc_now


class OperationAuditLog(IdMixin, Base):
    """由 B 显式提交的只追加操作审计记录。"""

    __tablename__ = "operation_audit_log"
    __table_args__ = (
        Index("ix_operation_audit_log_occurred_id", "occurred_at", "id"),
        Index(
            "ix_operation_audit_log_project_occurred_id",
            "project_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_operation_audit_log_actor_occurred_id",
            "actor_user_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_operation_audit_log_resource_occurred",
            "resource_type",
            "resource_code",
            "occurred_at",
        ),
        Index("ix_operation_audit_log_request_id", "request_id"),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
        comment="所属项目ID；系统级操作允许为空",
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=True,
        comment="操作用户ID；未登录或系统操作允许为空",
    )
    actor_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="操作人显示名称或标识快照"
    )
    action_code: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="由 B 定义的稳定操作代码"
    )
    resource_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="被操作资源类型代码"
    )
    resource_code: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="被操作资源的稳定业务编码"
    )
    result_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="由 B 定义的操作结果代码"
    )
    request_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="B 层请求追踪标识"
    )
    source: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="操作来源代码"
    )
    summary: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="不含敏感数据的操作摘要"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="业务发生时间（UTC）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, default=utc_now, comment="入库时间（UTC）"
    )
