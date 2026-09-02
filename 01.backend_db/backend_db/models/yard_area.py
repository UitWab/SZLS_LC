from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class YardArea(IdMixin, TimestampMixin, Base):
    """梁场区域。"""

    __tablename__ = "yard_area"

    area_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="区域稳定业务编码",
    )

    area_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="区域名称",
    )

    area_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="区域类型代码",
    )

    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "yard_area.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
        comment="父区域ID",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="展示排序值",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="是否启用",
    )

    remark: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="备注",
    )

    parent: Mapped[YardArea | None] = relationship(
        "YardArea",
        remote_side="YardArea.id",
        back_populates="children",
    )

    children: Mapped[list[YardArea]] = relationship(
        "YardArea",
        back_populates="parent",
    )

    positions: Mapped[list["BeamPosition"]] = relationship(
        "BeamPosition",
        back_populates="area",
    )