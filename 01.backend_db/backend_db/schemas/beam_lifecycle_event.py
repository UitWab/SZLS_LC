from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from backend_db.schemas.base import SchemaModel


Code = Annotated[str, Field(min_length=1, max_length=64)]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class BeamLifecycleEventType(StrEnum):
    BEAM_CREATED = "BEAM_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    POSITION_ASSIGNED = "POSITION_ASSIGNED"
    POSITION_MOVED = "POSITION_MOVED"
    POSITION_RELEASED = "POSITION_RELEASED"


class BeamLifecycleEventSummary(SchemaModel):
    id: int = Field(gt=0)
    project_code: str | None
    beam_code: str
    event_type: BeamLifecycleEventType
    status_before: str | None
    status_after: str | None
    source_position_code: str | None
    target_position_code: str | None
    work_order_code: str | None
    occurred_at: datetime


class BeamLifecycleEventRead(BeamLifecycleEventSummary):
    beam_id: int = Field(gt=0)
    source_position_id: int | None
    target_position_id: int | None
    work_order_id: int | None
    created_at: datetime


class BeamLifecycleEventSortField(StrEnum):
    ID = "id"
    EVENT_TYPE = "event_type"
    OCCURRED_AT = "occurred_at"
    CREATED_AT = "created_at"


class BeamLifecycleEventFilter(SchemaModel):
    project_code: Code | None = None
    beam_code: Code | None = None
    event_types: list[BeamLifecycleEventType] | None = None
    occurred_at_from: datetime | None = None
    occurred_at_to: datetime | None = None

    @field_validator("occurred_at_from", "occurred_at_to")
    @classmethod
    def normalize_bounds(cls, value):
        return _as_naive_utc(value)

    @model_validator(mode="after")
    def validate_range(self):
        if self.occurred_at_from and self.occurred_at_to:
            if self.occurred_at_from > self.occurred_at_to:
                raise ValueError("occurred_at_from 不能晚于 occurred_at_to")
        return self
