from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


AreaCode = Annotated[str, Field(min_length=1, max_length=64)]
AreaName = Annotated[str, Field(min_length=1, max_length=128)]
AreaType = Annotated[str, Field(min_length=1, max_length=32)]
Remark = Annotated[str, Field(max_length=500)]


class YardAreaCreate(SchemaModel):
    area_code: AreaCode
    area_name: AreaName
    area_type: AreaType
    parent_area_code: AreaCode | None = None
    sort_order: int = 0
    is_active: bool = True
    remark: Remark | None = None


class YardAreaUpdate(SchemaModel):
    area_name: AreaName | None = None
    area_type: AreaType | None = None
    parent_area_code: AreaCode | None = None
    sort_order: int | None = None
    remark: Remark | None = None

    @model_validator(mode="after")
    def validate_required_fields_are_not_null(self):
        for field_name in ("area_name", "area_type", "sort_order"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能设置为 null")
        return self


class YardAreaSummary(SchemaModel):
    id: int = Field(gt=0)
    area_code: str
    area_name: str
    area_type: str
    parent_area_code: str | None
    is_active: bool


class YardAreaRead(YardAreaSummary):
    parent_id: int | None
    sort_order: int
    remark: str | None
    created_at: datetime
    updated_at: datetime


class YardAreaTreeNode(YardAreaRead):
    children: list["YardAreaTreeNode"] = Field(default_factory=list)


class YardAreaSortField(StrEnum):
    ID = "id"
    AREA_CODE = "area_code"
    AREA_NAME = "area_name"
    SORT_ORDER = "sort_order"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class YardAreaFilter(SchemaModel):
    area_code: AreaCode | None = None
    area_type: AreaType | None = None
    parent_area_code: AreaCode | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None
