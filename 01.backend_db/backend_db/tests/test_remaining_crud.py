from uuid import uuid4

from backend_db.crud.beam import create_beam, get_beam_by_code
from backend_db.crud.beam_position import (
    create_beam_position,
    get_beam_position_by_code,
)
from backend_db.crud.beam_type import create_beam_type, get_beam_type_by_code
from backend_db.crud.yard_area import create_yard_area, get_yard_area_by_code
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork


def test_remaining_crud_functions_flush_but_do_not_commit():
    prefix = f"TEST_REMAINING_CRUD_{uuid4().hex[:8]}"

    with UnitOfWork() as unit:
        area = create_yard_area(
            unit.session,
            area_code=f"{prefix}_AREA",
            area_name="CRUD区域",
            area_type="test",
        )
        beam_type = create_beam_type(
            unit.session,
            type_code=f"{prefix}_TYPE",
            type_name="CRUD梁型",
        )
        position = create_beam_position(
            unit.session,
            position_code=f"{prefix}_POSITION",
            position_name="CRUD梁位",
            area_id=area.id,
        )
        beam = create_beam(
            unit.session,
            beam_code=f"{prefix}_BEAM",
            beam_type_id=beam_type.id,
            status="UNPRODUCED",
        )

        assert all(item.id is not None for item in (area, beam_type, position, beam))

    with SessionLocal() as session:
        assert get_yard_area_by_code(session, f"{prefix}_AREA") is None
        assert get_beam_type_by_code(session, f"{prefix}_TYPE") is None
        assert get_beam_position_by_code(session, f"{prefix}_POSITION") is None
        assert get_beam_by_code(session, f"{prefix}_BEAM") is None
