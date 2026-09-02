from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class Beam(IdMixin, TimestampMixin, Base):
    """梁档案及当前状态。"""

    __tablename__ = "beam"

    beam_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="梁稳定业务编号",
    )

    beam_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="梁名称",
    )

    beam_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "beam_type.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
        comment="梁型ID",
    )

    current_position_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "beam_position.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        unique=True,
        comment="当前梁位ID",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="梁当前状态代码",
    )

    production_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="生产日期",
    )

    remark: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="备注",
    )

    beam_type: Mapped["BeamType"] = relationship(
        "BeamType",
        back_populates="beams",
    )

    current_position: Mapped["BeamPosition | None"] = relationship(
        "BeamPosition",
        back_populates="current_beam",
    )