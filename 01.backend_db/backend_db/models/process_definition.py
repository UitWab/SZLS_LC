from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class ProcessDefinition(IdMixin, TimestampMixin, Base):
    """可配置的生产工序基础资料，不包含流程编排。"""

    __tablename__ = "process_definition"

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="所属项目ID；为空表示平台通用工序",
    )
    process_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="工序稳定业务编码"
    )
    process_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="工序名称"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="显示排序"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )
    remark: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="备注"
    )

    project: Mapped["Project | None"] = relationship(
        "Project", back_populates="process_definitions"
    )
