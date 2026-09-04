from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel
from backend_db.schemas.enums import BeamStatus


BeamCode = Annotated[str, Field(min_length=1, max_length=64)]
BeamName = Annotated[str, Field(min_length=1, max_length=128)]
BusinessCode = Annotated[str, Field(min_length=1, max_length=64)]
Remark = Annotated[str, Field(max_length=500)]


class BeamCreate(SchemaModel):
    beam_code: BeamCode
    beam_name: BeamName | None = None
    beam_type_code: BusinessCode
    status: BeamStatus = BeamStatus.UNPRODUCED
    production_date: date | None = None
    remark: Remark | None = None


class BeamUpdate(SchemaModel):
    beam_name: BeamName | None = None
    beam_type_code: BusinessCode | None = None
    production_date: date | None = None
    remark: Remark | None = None

    @model_validator(mode="after")
    def validate_beam_type_code_is_not_null(self):
        if "beam_type_code" in self.model_fields_set and self.beam_type_code is None:
            raise ValueError("beam_type_code 不能设置为 null")
        return self


class BeamStatusChange(SchemaModel):
    status: BeamStatus


class BeamPositionCommand(SchemaModel):
    position_code: BusinessCode


class BeamSummary(SchemaModel):
    id: int = Field(gt=0)
    beam_code: str
    beam_name: str | None
    beam_type_code: str
    beam_type_name: str
    status: BeamStatus
    current_position_code: str | None
    is_positioned: bool


class BeamRead(BeamSummary):
    beam_type_id: int = Field(gt=0)
    current_position_id: int | None
    current_position_name: str | None
    current_area_code: str | None
    current_area_name: str | None
    production_date: date | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class BeamSortField(StrEnum):
    ID = "id"
    BEAM_CODE = "beam_code"
    BEAM_NAME = "beam_name"
    STATUS = "status"
    PRODUCTION_DATE = "production_date"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class BeamFilter(SchemaModel):
    beam_code: BeamCode | None = None
    beam_type_code: BusinessCode | None = None
    statuses: list[BeamStatus] | None = None
    current_position_code: BusinessCode | None = None
    area_code: BusinessCode | None = None
    is_positioned: bool | None = None
    production_date_from: date | None = None
    production_date_to: date | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    updated_at_from: datetime | None = None
    updated_at_to: datetime | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        pairs = (
            ("production_date_from", "production_date_to"),
            ("created_at_from", "created_at_to"),
            ("updated_at_from", "updated_at_to"),
        )
        for start_name, end_name in pairs:
            start = getattr(self, start_name)
            end = getattr(self, end_name)
            if start is not None and end is not None and start > end:
                raise ValueError(f"{start_name} 不能晚于 {end_name}")
        return self
