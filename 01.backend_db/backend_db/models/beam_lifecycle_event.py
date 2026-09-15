from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, utc_now


class BeamLifecycleEvent(IdMixin, Base):
    """梁创建、状态变化和梁位变化的只追加事实记录。"""

    __tablename__ = "beam_lifecycle_event"
    __table_args__ = (
        Index(
            "ix_beam_event_project_occurred_id",
            "project_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_beam_event_beam_occurred_id",
            "beam_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_beam_event_project_id",
            "project_id",
            "id",
        ),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )
    beam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("beam.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_position_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_position.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_position_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_position.id", ondelete="RESTRICT"),
        nullable=True,
    )
    work_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_position_work_order.id", ondelete="RESTRICT"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=utc_now,
        comment="创建时间（UTC）",
    )

    project = relationship("Project")
    beam = relationship("Beam")
    source_position = relationship(
        "BeamPosition",
        foreign_keys=[source_position_id],
    )
    target_position = relationship(
        "BeamPosition",
        foreign_keys=[target_position_id],
    )
    work_order = relationship("BeamPositionWorkOrder")


class BeamLifecycleEventStreamLock(Base):
    """仅用于串行化同一项目范围内的生命周期事件写入。"""

    __tablename__ = "beam_lifecycle_event_stream_lock"

    scope_key: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )
