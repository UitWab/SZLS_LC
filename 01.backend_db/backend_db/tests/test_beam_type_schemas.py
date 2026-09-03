from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend_db.models import BeamType
from backend_db.schemas import (
    BeamTypeCreate,
    BeamTypeFilter,
    BeamTypeRead,
    BeamTypeSortField,
    BeamTypeUpdate,
)


def test_beam_type_create_applies_defaults_and_normalizes_strings():
    data = BeamTypeCreate(
        type_code="  T32  ",
        type_name="  32米箱梁  ",
    )

    assert data.type_code == "T32"
    assert data.type_name == "32米箱梁"
    assert data.is_active is True


@pytest.mark.parametrize(
    "values",
    [
        {"type_code": "", "type_name": "测试梁型"},
        {"type_code": "T32", "type_name": "   "},
        {"type_code": "T32", "type_name": "测试梁型", "length_mm": -1},
        {"type_code": "T32", "type_name": "测试梁型", "weight_kg": -1},
        {
            "type_code": "T32",
            "type_name": "测试梁型",
            "length_mm": "1234567890.123",
        },
    ],
)
def test_beam_type_create_rejects_invalid_values(values):
    with pytest.raises(ValidationError):
        BeamTypeCreate(**values)


def test_beam_type_update_distinguishes_unset_and_explicit_null():
    empty_update = BeamTypeUpdate()
    nullable_update = BeamTypeUpdate(description=None)

    assert empty_update.model_fields_set == set()
    assert nullable_update.model_fields_set == {"description"}
    assert nullable_update.description is None

    with pytest.raises(ValidationError):
        BeamTypeUpdate(type_name=None)


def test_beam_type_filter_accepts_valid_ranges():
    filters = BeamTypeFilter(
        length_mm_min="30000.000",
        length_mm_max="40000.000",
        is_active=True,
    )

    assert filters.length_mm_min == Decimal("30000.000")
    assert filters.length_mm_max == Decimal("40000.000")


def test_beam_type_filter_rejects_reversed_ranges():
    with pytest.raises(ValidationError):
        BeamTypeFilter(
            weight_kg_min="1000.000",
            weight_kg_max="999.999",
        )


def test_beam_type_read_can_be_built_from_orm_without_returning_orm():
    timestamp = datetime(2026, 9, 3, 8, 30, 0)
    model = BeamType(
        id=1,
        type_code="T32",
        type_name="32米箱梁",
        length_mm=Decimal("32000.000"),
        width_mm=Decimal("2400.000"),
        height_mm=Decimal("2200.000"),
        weight_kg=Decimal("78000.000"),
        description=None,
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )

    result = BeamTypeRead.model_validate(model)

    assert isinstance(result, BeamTypeRead)
    assert not isinstance(result, BeamType)
    assert result.type_code == "T32"
    assert result.model_dump(mode="json")["length_mm"] == "32000.000"


def test_beam_type_sort_fields_are_restricted_to_allowlist():
    assert {field.value for field in BeamTypeSortField} == {
        "id",
        "type_code",
        "type_name",
        "created_at",
        "updated_at",
    }

    with pytest.raises(ValueError):
        BeamTypeSortField("description")
