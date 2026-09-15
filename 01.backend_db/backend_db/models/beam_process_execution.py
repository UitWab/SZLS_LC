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


class BeamProcessExecution(IdMixin, TimestampMixin, Base):
    """一片梁在一道工序上的一次已结束执行事实。"""

    __tablename__ = "beam_process_execution"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_record_id",
            name="uq_beam_process_execution_source_external",
        ),
        UniqueConstraint(
            "supersedes_execution_id",
            name="uq_beam_process_execution_supersedes",
        ),
        CheckConstraint(
            "finished_at >= started_at",
            name="ck_beam_process_execution_time_order",
        ),
        CheckConstraint(
            "(is_voided = 0 AND voided_at IS NULL AND voided_by_user_id IS NULL "
            "AND voided_by_name IS NULL AND void_reason IS NULL) OR "
            "(is_voided = 1 AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_beam_process_execution_void_fields",
        ),
        Index(
            "ix_beam_process_execution_project_finished_id",
            "project_id",
            "finished_at",
            "id",
        ),
        Index(
            "ix_beam_process_execution_beam_finished_id",
            "beam_id",
            "finished_at",
            "id",
        ),
        Index(
            "ix_beam_process_execution_process_finished_id",
            "process_definition_id",
            "finished_at",
            "id",
        ),
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )
    execution_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    beam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("beam.id", ondelete="RESTRICT"), nullable=False
    )
    process_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("process_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_code: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supersedes_execution_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("beam_process_execution.id", ondelete="RESTRICT"),
        nullable=True,
    )
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
    process_definition = relationship("ProcessDefinition")
    actor_user = relationship("AppUser", foreign_keys=[actor_user_id])
    voided_by_user = relationship("AppUser", foreign_keys=[voided_by_user_id])
    supersedes_execution = relationship(
        "BeamProcessExecution",
        remote_side="BeamProcessExecution.id",
        foreign_keys=[supersedes_execution_id],
    )
