from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


BusinessCode = Annotated[str, Field(min_length=1, max_length=64)]
TypeName = Annotated[str, Field(min_length=1, max_length=128)]
Dimension = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=3),
]
Description = Annotated[str, Field(max_length=500)]


class BeamTypeCreate(SchemaModel):
    type_code: BusinessCode
    type_name: TypeName
    length_mm: Dimension | None = None
    width_mm: Dimension | None = None
    height_mm: Dimension | None = None
    weight_kg: Dimension | None = None
    description: Description | None = None
    is_active: bool = True


class BeamTypeUpdate(SchemaModel):
    """梁型部分更新；通过 model_fields_set 识别实际提交的字段。"""

    type_name: TypeName | None = None
    length_mm: Dimension | None = None
    width_mm: Dimension | None = None
    height_mm: Dimension | None = None
    weight_kg: Dimension | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def validate_required_fields_are_not_null(self):
        if "type_name" in self.model_fields_set and self.type_name is None:
            raise ValueError("type_name 不能设置为 null")

        return self


class BeamTypeSummary(SchemaModel):
    id: int = Field(gt=0)
    type_code: str
    type_name: str
    is_active: bool


class BeamTypeRead(BeamTypeSummary):
    length_mm: Decimal | None
    width_mm: Decimal | None
    height_mm: Decimal | None
    weight_kg: Decimal | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class BeamTypeSortField(StrEnum):
    ID = "id"
    TYPE_CODE = "type_code"
    TYPE_NAME = "type_name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class BeamTypeFilter(SchemaModel):
    type_code: BusinessCode | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    length_mm_min: Dimension | None = None
    length_mm_max: Dimension | None = None
    width_mm_min: Dimension | None = None
    width_mm_max: Dimension | None = None
    height_mm_min: Dimension | None = None
    height_mm_max: Dimension | None = None
    weight_kg_min: Dimension | None = None
    weight_kg_max: Dimension | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        range_pairs = (
            ("length_mm_min", "length_mm_max"),
            ("width_mm_min", "width_mm_max"),
            ("height_mm_min", "height_mm_max"),
            ("weight_kg_min", "weight_kg_max"),
        )

        for minimum_field, maximum_field in range_pairs:
            minimum = getattr(self, minimum_field)
            maximum = getattr(self, maximum_field)

            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(
                    f"{minimum_field} 不能大于 {maximum_field}"
                )

        return self
