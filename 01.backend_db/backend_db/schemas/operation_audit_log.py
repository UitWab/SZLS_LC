from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel


ProjectCode = Annotated[str, Field(min_length=1, max_length=64)]
ActorName = Annotated[str, Field(min_length=1, max_length=128)]
ActionCode = Annotated[str, Field(min_length=1, max_length=64)]
ResourceType = Annotated[str, Field(min_length=1, max_length=64)]
ResourceCode = Annotated[str, Field(min_length=1, max_length=128)]
ResultCode = Annotated[str, Field(min_length=1, max_length=32)]
RequestId = Annotated[str, Field(min_length=1, max_length=128)]
SourceCode = Annotated[str, Field(min_length=1, max_length=32)]
Summary = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class OperationAuditLogCreate(SchemaModel):
    project_code: ProjectCode | None = None
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: ActorName | None = None
    action_code: ActionCode
    resource_type: ResourceType
    resource_code: ResourceCode | None = None
    result_code: ResultCode
    request_id: RequestId | None = None
    source: SourceCode | None = None
    summary: Summary | None = None
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return _as_naive_utc(value)


class OperationAuditLogSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str | None
    actor_user_id: int | None
    actor_name: str | None
    action_code: str
    resource_type: str
    resource_code: str | None
    result_code: str
    occurred_at: datetime


class OperationAuditLogRead(OperationAuditLogSummary):
    request_id: str | None
    source: str | None
    summary: str | None
    created_at: datetime


class OperationAuditLogSortField(StrEnum):
    ID = "id"
    ACTION_CODE = "action_code"
    RESOURCE_TYPE = "resource_type"
    OCCURRED_AT = "occurred_at"
    CREATED_AT = "created_at"


class OperationAuditLogScope(StrEnum):
    SYSTEM = "SYSTEM"
    PROJECT = "PROJECT"
    ALL = "ALL"


class OperationAuditLogFilter(SchemaModel):
    scope: OperationAuditLogScope
    project_code: ProjectCode | None = None
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: ActorName | None = None
    action_code: ActionCode | None = None
    resource_type: ResourceType | None = None
    resource_code: ResourceCode | None = None
    result_code: ResultCode | None = None
    request_id: RequestId | None = None
    source: SourceCode | None = None
    occurred_at_from: datetime | None = None
    occurred_at_to: datetime | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == OperationAuditLogScope.PROJECT:
            if self.project_code is None:
                raise ValueError("PROJECT 范围必须提供 project_code")
        elif self.project_code is not None:
            raise ValueError("只有 PROJECT 范围可以提供 project_code")
        return self

    @field_validator("occurred_at_from", "occurred_at_to")
    @classmethod
    def normalize_occurred_at_bounds(cls, value: datetime | None) -> datetime | None:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_occurred_at_range(self):
        if (
            self.occurred_at_from is not None
            and self.occurred_at_to is not None
            and self.occurred_at_from > self.occurred_at_to
        ):
            raise ValueError("occurred_at_from 不能晚于 occurred_at_to")
        return self
