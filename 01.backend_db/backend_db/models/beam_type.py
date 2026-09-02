from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class BeamType(IdMixin, TimestampMixin, Base):
    """梁型档案。"""

    __tablename__ = "beam_type"

    type_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="梁型稳定业务编码",
    )

    type_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="梁型名称",
    )

    length_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="标称长度，单位mm",
    )

    width_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="标称宽度，单位mm",
    )

    height_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="标称高度，单位mm",
    )

    weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="标称质量，单位kg",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="梁型描述",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="是否启用",
    )

    beams: Mapped[list["Beam"]] = relationship(
        "Beam",
        back_populates="beam_type",
    )