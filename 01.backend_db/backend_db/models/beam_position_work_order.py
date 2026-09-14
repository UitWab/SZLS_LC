from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class BeamPositionWorkOrder(IdMixin, TimestampMixin, Base):
    """梁场内部入位、移位和出位任务。"""

    __tablename__ = "beam_position_work_order"
    __table_args__ = (
        Index("ix_bpw_order_project_status_id", "project_id", "status", "id"),
        Index("ix_bpw_order_beam_status", "beam_id", "status"),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=True
    )
    work_order_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    beam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("beam.id", ondelete="RESTRICT"), nullable=False
    )
    source_position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("beam_position.id", ondelete="RESTRICT"), nullable=True
    )
    target_position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("beam_position.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    planned_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project = relationship("Project")
    beam = relationship("Beam")
    source_position = relationship("BeamPosition", foreign_keys=[source_position_id])
    target_position = relationship("BeamPosition", foreign_keys=[target_position_id])
