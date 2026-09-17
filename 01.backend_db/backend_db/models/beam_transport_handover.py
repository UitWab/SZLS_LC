from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class BeamTransportHandover(IdMixin, TimestampMixin, Base):
    """一片梁在出场、转交或到场时的一次交接事实。"""

    __tablename__ = "beam_transport_handover"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_transport_handover_source_external",
        ),
        CheckConstraint(
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_transport_handover_void_fields",
        ),
        Index(
            "ix_beam_transport_handover_project_occurred_id",
            "project_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_beam_transport_handover_beam_occurred_id",
            "beam_id",
            "occurred_at",
            "id",
        ),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )
    handover_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    beam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("beam.id", ondelete="RESTRICT"), nullable=False
    )
    handover_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_code: Mapped[str] = mapped_column(String(32), nullable=False)
    from_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vehicle_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voided_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    voided_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project = relationship("Project")
    beam = relationship("Beam")
    actor_user = relationship("AppUser", foreign_keys=[actor_user_id])
    voided_by_user = relationship("AppUser", foreign_keys=[voided_by_user_id])
