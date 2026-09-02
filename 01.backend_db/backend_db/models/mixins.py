from datetime import datetime, timezone

from sqlalchemy import BigInteger
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """
    返回无时区标记的 UTC 时间。

    MySQL DATETIME 本身不保存时区信息，
    因此项目统一约定所有 DATETIME 业务时间均表示 UTC。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IdMixin:
    """统一 BIGINT 自增主键。"""

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="技术主键",
    )


class TimestampMixin:
    """统一创建时间和更新时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=utc_now,
        comment="创建时间（UTC）",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间（UTC）",
    )