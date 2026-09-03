import pytest

from backend_db.exceptions import (
    BackendDBError,
    BeamNotFoundError,
    InvalidBeamStatusError,
    InvalidDataError,
    PositionOccupiedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend_db.schemas import BEAM_STATUS_LABELS, BeamStatus


EXPECTED_STATUS_CODES = {
    "UNPRODUCED",
    "REBAR_BINDING",
    "REBAR_CHECK",
    "FORMWORK_CHECK",
    "CONCRETE_CASTING",
    "CURING",
    "TENSION_GROUTING",
    "QUALITY_ACCEPTED",
    "STORED",
    "READY_TO_SHIP",
    "TRANSPORTING",
    "ARRIVED",
    "ERECTING",
    "COMPLETED",
}


def test_beam_status_codes_are_stable_strings():
    assert {status.value for status in BeamStatus} == EXPECTED_STATUS_CODES
    assert str(BeamStatus.CURING) == "CURING"


def test_every_beam_status_has_a_display_label():
    assert set(BEAM_STATUS_LABELS) == set(BeamStatus)
    assert all(BEAM_STATUS_LABELS[status] for status in BeamStatus)


@pytest.mark.parametrize(
    ("error_type", "parent_type", "code"),
    [
        (BeamNotFoundError, ResourceNotFoundError, "beam_not_found"),
        (PositionOccupiedError, ResourceConflictError, "position_occupied"),
        (InvalidBeamStatusError, InvalidDataError, "invalid_beam_status"),
    ],
)
def test_public_exceptions_have_stable_hierarchy_and_codes(
    error_type,
    parent_type,
    code,
):
    error = error_type("测试异常")

    assert isinstance(error, BackendDBError)
    assert isinstance(error, parent_type)
    assert error.code == code
    assert str(error) == "测试异常"
