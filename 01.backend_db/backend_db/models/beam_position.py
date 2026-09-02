from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class BeamPosition(IdMixin, TimestampMixin, Base):
    """最小、唯一、单梁占用的物理梁位。"""

    __tablename__ = "beam_position"

    position_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="梁位稳定业务编码",
    )

    position_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="梁位名称",
    )

    area_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "yard_area.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
        comment="所属梁场区域ID",
    )

    x_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3),
        nullable=True,
        comment="场地X坐标，单位mm",
    )

    y_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3),
        nullable=True,
        comment="场地Y坐标，单位mm",
    )

    z_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3),
        nullable=True,
        comment="场地Z坐标，单位mm",
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

    area: Mapped["YardArea"] = relationship(
        "YardArea",
        back_populates="positions",
    )

    current_beam: Mapped["Beam | None"] = relationship(
        "Beam",
        back_populates="current_position",
        uselist=False,
    )