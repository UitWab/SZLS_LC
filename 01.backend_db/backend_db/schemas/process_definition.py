from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


Code = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Remark = Annotated[str, Field(max_length=500)]


class ProcessDefinitionCreate(SchemaModel):
    process_code: Code
    process_name: Name
    project_code: Code | None = None
    sort_order: int = 0
    is_active: bool = True
    remark: Remark | None = None


class ProcessDefinitionUpdate(SchemaModel):
    process_name: Name | None = None
    project_code: Code | None = None
    sort_order: int | None = None
    remark: Remark | None = None

    @model_validator(mode="after")
    def validate_required_fields_are_not_null(self):
        for field_name in ("process_name", "sort_order"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能设置为 null")
        return self


class ProcessDefinitionSummary(SchemaModel):
    id: int = Field(gt=0)
    process_code: str
    process_name: str
    project_code: str | None
    sort_order: int
    is_active: bool


class ProcessDefinitionRead(ProcessDefinitionSummary):
    project_id: int | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class ProcessDefinitionFilter(SchemaModel):
    process_code: Code | None = None
    project_code: Code | None = None
    include_global: bool = False
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class ProcessDefinitionSortField(StrEnum):
    ID = "id"
    PROCESS_CODE = "process_code"
    PROCESS_NAME = "process_name"
    SORT_ORDER = "sort_order"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
