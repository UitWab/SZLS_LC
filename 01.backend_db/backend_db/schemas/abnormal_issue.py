from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel
from backend_db.schemas.beam_process_execution import RecordSource


Code = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Title = Annotated[str, Field(min_length=1, max_length=128)]
Text500 = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class AbnormalIssueCategory(StrEnum):
    PROGRESS = "PROGRESS"
    PRODUCTION = "PRODUCTION"
    QUALITY = "QUALITY"
    STORAGE = "STORAGE"
    LOGISTICS = "LOGISTICS"
    EQUIPMENT = "EQUIPMENT"
    SAFETY = "SAFETY"
    INSPECTION = "INSPECTION"


class AbnormalIssueSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AbnormalIssueStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class AbnormalIssueCreate(SchemaModel):
    issue_code: Code
    project_code: Code
    beam_code: Code | None = None
    device_code: Code | None = None
    category_code: AbnormalIssueCategory
    issue_type_code: Code
    severity: AbnormalIssueSeverity
    title: Title
    message: Text500
    occurred_at: datetime
    reported_by_user_id: int | None = Field(default=None, gt=0)
    reported_by_name: Name | None = None
    source: RecordSource = RecordSource.MANUAL
    external_record_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _as_naive_utc(value)


class AbnormalIssueActorAction(SchemaModel):
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: Name | None = None

    @model_validator(mode="after")
    def validate_actor(self):
        if self.actor_user_id is None and self.actor_name is None:
            raise ValueError("actor_user_id 和 actor_name 至少提供一个")
        return self


class AbnormalIssueResolve(AbnormalIssueActorAction):
    resolution_summary: Text500


class AbnormalIssueClose(AbnormalIssueActorAction):
    close_note: Text500 | None = None


class AbnormalIssueSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str
    issue_code: str
    beam_code: str | None
    device_code: str | None
    category_code: AbnormalIssueCategory
    issue_type_code: str
    severity: AbnormalIssueSeverity
    status: AbnormalIssueStatus
    title: str
    occurred_at: datetime
    source: RecordSource


class AbnormalIssueRead(AbnormalIssueSummary):
    message: str
    reported_by_user_id: int | None
    reported_by_name: str | None
    external_record_id: str | None
    processing_started_at: datetime | None
    processing_by_user_id: int | None
    processing_by_name: str | None
    resolved_at: datetime | None
    resolved_by_user_id: int | None
    resolved_by_name: str | None
    resolution_summary: str | None
    closed_at: datetime | None
    closed_by_user_id: int | None
    closed_by_name: str | None
    close_note: str | None
    created_at: datetime
    updated_at: datetime


class AbnormalIssueFilter(SchemaModel):
    project_code: Code
    issue_code: Code | None = None
    beam_code: Code | None = None
    device_code: Code | None = None
    category_codes: list[AbnormalIssueCategory] | None = None
    issue_type_codes: list[Code] | None = None
    severities: list[AbnormalIssueSeverity] | None = None
    statuses: list[AbnormalIssueStatus] | None = None
    sources: list[RecordSource] | None = None
    occurred_at_from: datetime | None = None
    occurred_at_to: datetime | None = None
    external_record_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @field_validator("occurred_at_from", "occurred_at_to")
    @classmethod
    def normalize_bounds(cls, value: datetime | None) -> datetime | None:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_range(self):
        if self.occurred_at_from and self.occurred_at_to:
            if self.occurred_at_from > self.occurred_at_to:
                raise ValueError("occurred_at_from 不能晚于 occurred_at_to")
        return self


class AbnormalIssueSortField(StrEnum):
    ID = "id"
    ISSUE_CODE = "issue_code"
    CATEGORY_CODE = "category_code"
    SEVERITY = "severity"
    STATUS = "status"
    OCCURRED_AT = "occurred_at"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
