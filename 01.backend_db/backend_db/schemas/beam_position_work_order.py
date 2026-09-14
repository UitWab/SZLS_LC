from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel

Code = Annotated[str, Field(min_length=1, max_length=64)]
Remark = Annotated[str, Field(min_length=1, max_length=500)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class BeamPositionWorkOrderType(StrEnum):
    PLACE = "PLACE"
    MOVE = "MOVE"
    RELEASE = "RELEASE"


class BeamPositionWorkOrderStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class BeamPositionWorkOrderCreate(SchemaModel):
    work_order_code: Code
    project_code: Code | None = None
    beam_code: Code
    order_type: BeamPositionWorkOrderType
    target_position_code: Code | None = None
    planned_at: datetime | None = None
    remark: Remark | None = None

    @field_validator("planned_at")
    @classmethod
    def normalize_planned_at(cls, value):
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_positions(self):
        needs_target = self.order_type in {
            BeamPositionWorkOrderType.PLACE,
            BeamPositionWorkOrderType.MOVE,
        }
        if needs_target and self.target_position_code is None:
            raise ValueError("PLACE 和 MOVE 工单必须提供 target_position_code")
        if self.order_type == BeamPositionWorkOrderType.RELEASE and self.target_position_code:
            raise ValueError("RELEASE 工单不能提供 target_position_code")
        return self


class BeamPositionWorkOrderSummary(SchemaModel):
    id: int
    project_code: str | None
    work_order_code: str
    order_type: BeamPositionWorkOrderType
    beam_code: str
    source_position_code: str | None
    target_position_code: str | None
    status: BeamPositionWorkOrderStatus
    planned_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class BeamPositionWorkOrderRead(BeamPositionWorkOrderSummary):
    beam_id: int
    source_position_id: int | None
    target_position_id: int | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class BeamPositionWorkOrderFilter(SchemaModel):
    project_code: Code | None = None
    include_global: bool = False
    work_order_code: Code | None = None
    beam_code: Code | None = None
    order_types: list[BeamPositionWorkOrderType] | None = None
    statuses: list[BeamPositionWorkOrderStatus] | None = None
    source_position_code: Code | None = None
    target_position_code: Code | None = None
    planned_at_from: datetime | None = None
    planned_at_to: datetime | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @field_validator("planned_at_from", "planned_at_to")
    @classmethod
    def normalize_bounds(cls, value):
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_range(self):
        if self.planned_at_from and self.planned_at_to:
            if self.planned_at_from > self.planned_at_to:
                raise ValueError("planned_at_from 不能晚于 planned_at_to")
        return self


class BeamPositionWorkOrderSortField(StrEnum):
    ID = "id"
    WORK_ORDER_CODE = "work_order_code"
    STATUS = "status"
    PLANNED_AT = "planned_at"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
