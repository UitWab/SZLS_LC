from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


ProjectCode = Annotated[str, Field(min_length=1, max_length=64)]
ProjectName = Annotated[str, Field(min_length=1, max_length=128)]
Remark = Annotated[str, Field(max_length=500)]


class ProjectCreate(SchemaModel):
    project_code: ProjectCode
    project_name: ProjectName
    is_active: bool = True
    remark: Remark | None = None


class ProjectUpdate(SchemaModel):
    project_name: ProjectName | None = None
    remark: Remark | None = None

    @model_validator(mode="after")
    def validate_project_name_is_not_null(self):
        if "project_name" in self.model_fields_set and self.project_name is None:
            raise ValueError("project_name 不能设置为 null")
        return self


class ProjectSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str
    project_name: str
    is_active: bool


class ProjectRead(ProjectSummary):
    remark: str | None
    created_at: datetime
    updated_at: datetime


class ProjectSortField(StrEnum):
    ID = "id"
    PROJECT_CODE = "project_code"
    PROJECT_NAME = "project_name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class ProjectFilter(SchemaModel):
    project_code: ProjectCode | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None
