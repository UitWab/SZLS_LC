from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import Field

from backend_db.schemas.base import SchemaModel


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class PageRequest(SchemaModel):
    """面向管理查询的页码分页参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    include_total: bool = True

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


ItemT = TypeVar("ItemT")


class PageResult(SchemaModel, Generic[ItemT]):
    """稳定的分页返回结构，不包含 ORM 对象。"""

    items: list[ItemT]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int | None = Field(default=None, ge=0)
    has_next: bool
    has_previous: bool


class CursorPageRequest(SchemaModel):
    """为后续数字孪生增量同步预留的游标分页参数。"""

    cursor: str | None = Field(default=None, max_length=512)
    limit: int = Field(default=100, ge=1, le=100)


class CursorPageResult(SchemaModel, Generic[ItemT]):
    items: list[ItemT]
    next_cursor: str | None
    has_more: bool
