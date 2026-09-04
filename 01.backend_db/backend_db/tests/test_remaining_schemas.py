from datetime import date, datetime

import pytest
from pydantic import ValidationError

from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamPositionCreate,
    BeamPositionUpdate,
    BeamStatus,
    BeamUpdate,
    YardAreaCreate,
    YardAreaUpdate,
)


def test_yard_area_schema_normalizes_and_protects_required_fields():
    data = YardAreaCreate(
        area_code="  STORAGE_A  ",
        area_name="  存梁区A  ",
        area_type=" storage ",
    )
    assert data.area_code == "STORAGE_A"
    assert data.area_name == "存梁区A"
    assert data.area_type == "storage"
    assert data.is_active is True

    with pytest.raises(ValidationError):
        YardAreaUpdate(area_name=None)


def test_yard_area_update_can_explicitly_clear_parent():
    data = YardAreaUpdate(parent_area_code=None)
    assert data.model_fields_set == {"parent_area_code"}


def test_beam_position_schema_validates_precision_and_area():
    data = BeamPositionCreate(
        position_code="P001",
        area_code="A001",
        x_mm="-1200.500",
    )
    assert str(data.x_mm) == "-1200.500"

    with pytest.raises(ValidationError):
        BeamPositionCreate(
            position_code="P001",
            area_code="A001",
            x_mm="123456789012.345",
        )

    with pytest.raises(ValidationError):
        BeamPositionUpdate(area_code=None)


def test_beam_create_defaults_to_unproduced_and_rejects_unknown_status():
    data = BeamCreate(beam_code="B001", beam_type_code="T001")
    assert data.status is BeamStatus.UNPRODUCED

    with pytest.raises(ValidationError):
        BeamCreate(
            beam_code="B001",
            beam_type_code="T001",
            status="UNKNOWN_STATUS",
        )


def test_beam_update_cannot_change_status_position_or_code():
    for values in (
        {"status": BeamStatus.STORED},
        {"current_position_id": 1},
        {"beam_code": "CHANGED"},
    ):
        with pytest.raises(ValidationError):
            BeamUpdate(**values)


@pytest.mark.parametrize(
    "values",
    [
        {
            "production_date_from": date(2026, 2, 1),
            "production_date_to": date(2026, 1, 1),
        },
        {
            "created_at_from": datetime(2026, 2, 1),
            "created_at_to": datetime(2026, 1, 1),
        },
    ],
)
def test_beam_filter_rejects_reversed_ranges(values):
    with pytest.raises(ValidationError):
        BeamFilter(**values)
