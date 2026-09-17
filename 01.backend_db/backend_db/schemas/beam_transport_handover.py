from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel
from backend_db.schemas.beam_process_execution import RecordSource


Code = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Location = Annotated[str, Field(min_length=1, max_length=255)]
Text128 = Annotated[str, Field(min_length=1, max_length=128)]
Text500 = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class TransportHandoverType(StrEnum):
    OUTBOUND = "OUTBOUND"
    TRANSFER = "TRANSFER"
    ARRIVAL = "ARRIVAL"


class TransportHandoverResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class BeamTransportHandoverCreate(SchemaModel):
    handover_code: Code
    project_code: Code | None = None
    beam_code: Code
    handover_type: TransportHandoverType
    result_code: TransportHandoverResult
    from_location: Location | None = None
    to_location: Location | None = None
    carrier_name: Name | None = None
    vehicle_no: Code | None = None
    sender_name: Name | None = None
    receiver_name: Name | None = None
    occurred_at: datetime
    actor_user_id: int | None = Field(default=None, gt=0)
    actor_name: Name | None = None
    source: RecordSource = RecordSource.MANUAL
    external_record_id: Text128 | None = None
    remark: Text500 | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_handover(self):
        if self.actor_user_id is None and self.actor_name is None:
            raise ValueError("actor_user_id 和 actor_name 至少提供一个")
        if self.handover_type == TransportHandoverType.OUTBOUND:
            if self.to_location is None:
                raise ValueError("OUTBOUND 必须提供 to_location")
        elif self.handover_type == TransportHandoverType.ARRIVAL:
            if self.from_location is None:
                raise ValueError("ARRIVAL 必须提供 from_location")
        elif self.from_location is None or self.to_location is None:
            raise ValueError("TRANSFER 必须同时提供 from_location 和 to_location")
        return self


class BeamTransportHandoverVoid(SchemaModel):
    voided_by_user_id: int | None = Field(default=None, gt=0)
    voided_by_name: Name | None = None
    void_reason: Text500

    @model_validator(mode="after")
    def validate_actor(self):
        if self.voided_by_user_id is None and self.voided_by_name is None:
            raise ValueError("voided_by_user_id 和 voided_by_name 至少提供一个")
        return self


class BeamTransportHandoverSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str | None
    handover_code: str
    beam_code: str
    handover_type: TransportHandoverType
    result_code: TransportHandoverResult
    from_location: str | None
    to_location: str | None
    carrier_name: str | None
    vehicle_no: str | None
    occurred_at: datetime
    actor_user_id: int | None
    actor_name: str | None
    source: RecordSource
    is_voided: bool


class BeamTransportHandoverRead(BeamTransportHandoverSummary):
    sender_name: str | None
    receiver_name: str | None
    external_record_id: str | None
    remark: str | None
    voided_at: datetime | None
    voided_by_user_id: int | None
    voided_by_name: str | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime


class BeamTransportHandoverFilter(SchemaModel):
    project_code: Code | None = None
    handover_code: Code | None = None
    beam_code: Code | None = None
    handover_types: list[TransportHandoverType] | None = None
    result_codes: list[TransportHandoverResult] | None = None
    sources: list[RecordSource] | None = None
    occurred_at_from: datetime | None = None
    occurred_at_to: datetime | None = None
    vehicle_no: Code | None = None
    carrier_name: Name | None = None
    actor_user_id: int | None = Field(default=None, gt=0)
    external_record_id: Text128 | None = None
    is_voided: bool | None = None
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


class BeamTransportHandoverSortField(StrEnum):
    ID = "id"
    HANDOVER_CODE = "handover_code"
    HANDOVER_TYPE = "handover_type"
    RESULT_CODE = "result_code"
    OCCURRED_AT = "occurred_at"
    CREATED_AT = "created_at"
