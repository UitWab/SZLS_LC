from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel
from backend_db.schemas.beam_process_execution import RecordSource


Code = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Text128 = Annotated[str, Field(min_length=1, max_length=128)]
Text500 = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class BeamQualityResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class BeamQualityItemResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BeamQualityInspectionItemCreate(SchemaModel):
    item_code: Code
    item_name: Name
    requirement_text: Text500 | None = None
    observed_value: Text128 | None = None
    unit: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    result_code: BeamQualityItemResult
    remark: Text500 | None = None


class BeamQualityInspectionCreate(SchemaModel):
    inspection_code: Code
    project_code: Code | None = None
    beam_code: Code
    process_code: Code | None = None
    process_execution_code: Code | None = None
    previous_inspection_code: Code | None = None
    inspection_type_code: Code
    result_code: BeamQualityResult
    inspected_at: datetime
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: Name | None = None
    source: RecordSource = RecordSource.MANUAL
    external_record_id: Text128 | None = None
    summary: Text500 | None = None
    items: list[BeamQualityInspectionItemCreate] = Field(default_factory=list)

    @field_validator("inspected_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_inspection(self):
        if self.actor_user_id is None and self.actor_name is None:
            raise ValueError("actor_user_id 和 actor_name 至少提供一个")
        if self.previous_inspection_code == self.inspection_code:
            raise ValueError("质量检查记录不能复检自身")
        item_codes = [item.item_code for item in self.items]
        if len(item_codes) != len(set(item_codes)):
            raise ValueError("同一次质量检查的 item_code 不能重复")
        if self.result_code == BeamQualityResult.PASS and any(
            item.result_code == BeamQualityItemResult.FAIL for item in self.items
        ):
            raise ValueError("存在失败检查项时整体结果不能为 PASS")
        return self


class BeamQualityInspectionVoid(SchemaModel):
    voided_by_user_id: int | None = Field(default=None, gt=0)
    voided_by_name: Name | None = None
    void_reason: Text500

    @model_validator(mode="after")
    def validate_actor(self):
        if self.voided_by_user_id is None and self.voided_by_name is None:
            raise ValueError("voided_by_user_id 和 voided_by_name 至少提供一个")
        return self


class BeamQualityInspectionItemRead(SchemaModel):
    id: int = Field(gt=0)
    item_code: str
    item_name: str
    requirement_text: str | None
    observed_value: str | None
    unit: str | None
    result_code: BeamQualityItemResult
    remark: str | None


class BeamQualityInspectionSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str | None
    inspection_code: str
    beam_code: str
    process_code: str | None
    process_execution_code: str | None
    previous_inspection_code: str | None
    inspection_type_code: str
    result_code: BeamQualityResult
    inspected_at: datetime
    actor_user_id: int | None
    actor_name: str | None
    source: RecordSource
    is_voided: bool


class BeamQualityInspectionRead(BeamQualityInspectionSummary):
    external_record_id: str | None
    summary: str | None
    items: list[BeamQualityInspectionItemRead]
    voided_at: datetime | None
    voided_by_user_id: int | None
    voided_by_name: str | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime


class BeamQualityInspectionFilter(SchemaModel):
    project_code: Code | None = None
    inspection_code: Code | None = None
    beam_code: Code | None = None
    process_code: Code | None = None
    process_execution_code: Code | None = None
    inspection_type_code: Code | None = None
    result_codes: list[BeamQualityResult] | None = None
    sources: list[RecordSource] | None = None
    inspected_at_from: datetime | None = None
    inspected_at_to: datetime | None = None
    is_reinspection: bool | None = None
    is_voided: bool | None = None
    actor_user_id: int | None = Field(default=None, gt=0)
    external_record_id: Text128 | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @field_validator("inspected_at_from", "inspected_at_to")
    @classmethod
    def normalize_bounds(cls, value: datetime | None) -> datetime | None:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_range(self):
        if self.inspected_at_from and self.inspected_at_to:
            if self.inspected_at_from > self.inspected_at_to:
                raise ValueError("inspected_at_from 不能晚于 inspected_at_to")
        return self


class BeamQualityInspectionSortField(StrEnum):
    ID = "id"
    INSPECTION_CODE = "inspection_code"
    INSPECTION_TYPE_CODE = "inspection_type_code"
    RESULT_CODE = "result_code"
    INSPECTED_AT = "inspected_at"
    CREATED_AT = "created_at"
