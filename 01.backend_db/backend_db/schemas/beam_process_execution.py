from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel


Code = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
ExternalId = Annotated[str, Field(min_length=1, max_length=128)]
Remark = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class BeamProcessResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class RecordSource(StrEnum):
    MANUAL = "MANUAL"
    SYSTEM = "SYSTEM"
    IMPORT = "IMPORT"
    DEVICE = "DEVICE"


class BeamProcessExecutionCreate(SchemaModel):
    execution_code: Code
    project_code: Code | None = None
    beam_code: Code
    process_code: Code
    result_code: BeamProcessResult
    started_at: datetime
    finished_at: datetime
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: Name | None = None
    source: RecordSource = RecordSource.MANUAL
    external_record_id: ExternalId | None = None
    supersedes_execution_code: Code | None = None
    remark: Remark | None = None

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_execution(self):
        if self.finished_at < self.started_at:
            raise ValueError("finished_at 不能早于 started_at")
        if self.actor_user_id is None and self.actor_name is None:
            raise ValueError("actor_user_id 和 actor_name 至少提供一个")
        if self.supersedes_execution_code == self.execution_code:
            raise ValueError("执行记录不能替代自身")
        return self


class BeamProcessExecutionVoid(SchemaModel):
    voided_by_user_id: int | None = Field(default=None, gt=0)
    voided_by_name: Name | None = None
    void_reason: Remark

    @model_validator(mode="after")
    def validate_actor(self):
        if self.voided_by_user_id is None and self.voided_by_name is None:
            raise ValueError("voided_by_user_id 和 voided_by_name 至少提供一个")
        return self


class BeamProcessExecutionSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str | None
    execution_code: str
    beam_code: str
    process_code: str
    result_code: BeamProcessResult
    started_at: datetime
    finished_at: datetime
    actor_user_id: int | None
    actor_name: str | None
    source: RecordSource
    is_voided: bool


class BeamProcessExecutionRead(BeamProcessExecutionSummary):
    external_record_id: str | None
    supersedes_execution_code: str | None
    remark: str | None
    voided_at: datetime | None
    voided_by_user_id: int | None
    voided_by_name: str | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime


class BeamProcessExecutionFilter(SchemaModel):
    project_code: Code | None = None
    execution_code: Code | None = None
    beam_code: Code | None = None
    process_code: Code | None = None
    result_codes: list[BeamProcessResult] | None = None
    sources: list[RecordSource] | None = None
    started_at_from: datetime | None = None
    started_at_to: datetime | None = None
    finished_at_from: datetime | None = None
    finished_at_to: datetime | None = None
    is_voided: bool | None = None
    is_correction: bool | None = None
    actor_user_id: int | None = Field(default=None, gt=0)
    external_record_id: ExternalId | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @field_validator(
        "started_at_from", "started_at_to", "finished_at_from", "finished_at_to"
    )
    @classmethod
    def normalize_bounds(cls, value: datetime | None) -> datetime | None:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.started_at_from and self.started_at_to:
            if self.started_at_from > self.started_at_to:
                raise ValueError("started_at_from 不能晚于 started_at_to")
        if self.finished_at_from and self.finished_at_to:
            if self.finished_at_from > self.finished_at_to:
                raise ValueError("finished_at_from 不能晚于 finished_at_to")
        return self


class BeamProcessExecutionSortField(StrEnum):
    ID = "id"
    EXECUTION_CODE = "execution_code"
    RESULT_CODE = "result_code"
    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    CREATED_AT = "created_at"
