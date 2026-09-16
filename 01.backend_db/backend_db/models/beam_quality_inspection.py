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


class BeamQualityInspection(IdMixin, TimestampMixin, Base):
    """对一片梁进行的一次独立质量检查事实。"""

    __tablename__ = "beam_quality_inspection"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_quality_inspection_source_external",
        ),
        CheckConstraint(
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_quality_inspection_void_fields",
        ),
        Index(
            "ix_beam_quality_inspection_project_inspected_id",
            "project_id",
            "inspected_at",
            "id",
        ),
        Index(
            "ix_beam_quality_inspection_beam_inspected_id",
            "beam_id",
            "inspected_at",
            "id",
        ),
        Index(
            "ix_beam_quality_inspection_process_inspected_id",
            "process_definition_id",
            "inspected_at",
            "id",
        ),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )
    inspection_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    beam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("beam.id", ondelete="RESTRICT"), nullable=False
    )
    process_definition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("process_definition.id", ondelete="RESTRICT"),
        nullable=True,
    )
    process_execution_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_process_execution.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    previous_inspection_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_quality_inspection.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    inspection_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    result_code: Mapped[str] = mapped_column(String(32), nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voided_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    voided_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project = relationship("Project")
    beam = relationship("Beam")
    process_definition = relationship("ProcessDefinition")
    process_execution = relationship("BeamProcessExecution")
    previous_inspection = relationship(
        "BeamQualityInspection",
        remote_side="BeamQualityInspection.id",
        foreign_keys=[previous_inspection_id],
    )
    actor_user = relationship("AppUser", foreign_keys=[actor_user_id])
    voided_by_user = relationship("AppUser", foreign_keys=[voided_by_user_id])
    items = relationship(
        "BeamQualityInspectionItem",
        back_populates="inspection",
        order_by="BeamQualityInspectionItem.item_code",
    )


class BeamQualityInspectionItem(IdMixin, Base):
    """质量检查记录中不可变的检查项快照。"""

    __tablename__ = "beam_quality_inspection_item"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            "item_code",
            name="uq_beam_quality_inspection_item_code",
        ),
    )

    inspection_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("beam_quality_inspection.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    item_code: Mapped[str] = mapped_column(
        String(64, collation="utf8mb4_bin"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_code: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)

    inspection = relationship("BeamQualityInspection", back_populates="items")
