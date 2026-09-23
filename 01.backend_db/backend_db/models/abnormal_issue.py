from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class AbnormalIssue(IdMixin, TimestampMixin, Base):
    """已经由业务方、外部系统或设备判定成立的异常事项。"""

    __tablename__ = "abnormal_issue"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_abnormal_issue_source_external",
        ),
        CheckConstraint(
            "(status = 'OPEN' "
            "AND processing_started_at IS NULL "
            "AND processing_by_user_id IS NULL "
            "AND processing_by_name IS NULL "
            "AND resolved_at IS NULL "
            "AND resolved_by_user_id IS NULL "
            "AND resolved_by_name IS NULL "
            "AND resolution_summary IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'IN_PROGRESS' "
            "AND processing_started_at IS NOT NULL "
            "AND (processing_by_user_id IS NOT NULL OR processing_by_name IS NOT NULL) "
            "AND resolved_at IS NULL "
            "AND resolved_by_user_id IS NULL "
            "AND resolved_by_name IS NULL "
            "AND resolution_summary IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'RESOLVED' "
            "AND resolved_at IS NOT NULL "
            "AND (resolved_by_user_id IS NOT NULL OR resolved_by_name IS NOT NULL) "
            "AND resolution_summary IS NOT NULL "
            "AND closed_at IS NULL "
            "AND closed_by_user_id IS NULL "
            "AND closed_by_name IS NULL "
            "AND close_note IS NULL) OR "
            "(status = 'CLOSED' "
            "AND resolved_at IS NOT NULL "
            "AND (resolved_by_user_id IS NOT NULL OR resolved_by_name IS NOT NULL) "
            "AND resolution_summary IS NOT NULL "
            "AND closed_at IS NOT NULL "
            "AND (closed_by_user_id IS NOT NULL OR closed_by_name IS NOT NULL))",
            name="ck_abnormal_issue_status_fields",
        ),
        CheckConstraint(
            "(processing_started_at IS NULL "
            "AND processing_by_user_id IS NULL "
            "AND processing_by_name IS NULL) OR "
            "(processing_started_at IS NOT NULL "
            "AND (processing_by_user_id IS NOT NULL OR processing_by_name IS NOT NULL))",
            name="ck_abnormal_issue_processing_actor",
        ),
        Index(
            "ix_abnormal_issue_project_occurred_id",
            "project_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_abnormal_issue_project_status_occurred_id",
            "project_id",
            "status",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_abnormal_issue_project_category_status_occurred_id",
            "project_id",
            "category_code",
            "status",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_abnormal_issue_beam_occurred_id",
            "beam_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_abnormal_issue_project_device_occurred_id",
            "project_id",
            "device_code",
            "occurred_at",
            "id",
        ),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False
    )
    issue_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    beam_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("beam.id", ondelete="RESTRICT"), nullable=True
    )
    device_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category_code: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    reported_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    reported_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True
    )
    processing_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    processing_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    resolved_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    closed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    close_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project = relationship("Project")
    beam = relationship("Beam")
    reported_by_user = relationship("AppUser", foreign_keys=[reported_by_user_id])
    processing_by_user = relationship("AppUser", foreign_keys=[processing_by_user_id])
    resolved_by_user = relationship("AppUser", foreign_keys=[resolved_by_user_id])
    closed_by_user = relationship("AppUser", foreign_keys=[closed_by_user_id])
