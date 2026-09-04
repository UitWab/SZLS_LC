from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


PositionCode = Annotated[str, Field(min_length=1, max_length=64)]
PositionName = Annotated[str, Field(min_length=1, max_length=128)]
AreaCode = Annotated[str, Field(min_length=1, max_length=64)]
Coordinate = Annotated[
    Decimal,
    Field(max_digits=14, decimal_places=3),
]
Remark = Annotated[str, Field(max_length=500)]


class BeamPositionCreate(SchemaModel):
    position_code: PositionCode
    position_name: PositionName | None = None
    area_code: AreaCode
    x_mm: Coordinate | None = None
    y_mm: Coordinate | None = None
    z_mm: Coordinate | None = None
    is_active: bool = True
    remark: Remark | None = None


class BeamPositionUpdate(SchemaModel):
    position_name: PositionName | None = None
    area_code: AreaCode | None = None
    x_mm: Coordinate | None = None
    y_mm: Coordinate | None = None
    z_mm: Coordinate | None = None
    remark: Remark | None = None

    @model_validator(mode="after")
    def validate_area_code_is_not_null(self):
        if "area_code" in self.model_fields_set and self.area_code is None:
            raise ValueError("area_code 不能设置为 null")
        return self


class BeamPositionSummary(SchemaModel):
    id: int = Field(gt=0)
    position_code: str
    position_name: str | None
    area_code: str
    area_name: str
    is_active: bool
    is_occupied: bool


class BeamPositionRead(BeamPositionSummary):
    area_id: int = Field(gt=0)
    x_mm: Decimal | None
    y_mm: Decimal | None
    z_mm: Decimal | None
    remark: str | None
    current_beam_code: str | None
    created_at: datetime
    updated_at: datetime


class BeamPositionSortField(StrEnum):
    ID = "id"
    POSITION_CODE = "position_code"
    POSITION_NAME = "position_name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class BeamPositionFilter(SchemaModel):
    position_code: PositionCode | None = None
    area_code: AreaCode | None = None
    is_active: bool | None = None
    is_occupied: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None
