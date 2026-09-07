from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    """平台管理的工程项目。"""

    __tablename__ = "project"

    project_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="项目稳定业务编码",
    )

    project_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="项目名称",
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

    beam_types: Mapped[list["BeamType"]] = relationship(
        "BeamType",
        back_populates="project",
    )

    yard_areas: Mapped[list["YardArea"]] = relationship(
        "YardArea",
        back_populates="project",
    )

    beams: Mapped[list["Beam"]] = relationship(
        "Beam",
        back_populates="project",
    )

    process_definitions: Mapped[list["ProcessDefinition"]] = relationship(
        "ProcessDefinition",
        back_populates="project",
    )
