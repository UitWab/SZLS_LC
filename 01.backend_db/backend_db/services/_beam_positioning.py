from backend_db.crud.beam import get_beam_by_code, set_beam_position
from backend_db.crud.beam_position import get_beam_at_position, get_beam_position_by_code
from backend_db.exceptions import (
    BeamAlreadyPositionedError,
    BeamNotFoundError,
    BeamPositionNotFoundError,
    InactiveResourceError,
    PositionOccupiedError,
)
from backend_db.services._project_scope import matches_project_scope


def get_locked_beam(unit, beam_code: str, *, project):
    beam = get_beam_by_code(unit.session, beam_code, for_update=True)
    if beam is None or not matches_project_scope(beam.project_id, project):
        raise BeamNotFoundError(f"梁不存在: beam_code={beam_code}")
    return beam


def get_active_position(unit, position_code: str, *, project_id: int | None):
    position = get_beam_position_by_code(unit.session, position_code, for_update=True)
    if position is None or position.area.project_id != project_id:
        raise BeamPositionNotFoundError(f"梁位不存在: position_code={position_code}")
    if not position.is_active:
        raise InactiveResourceError("目标梁位未启用")
    return position


def place_beam(unit, beam, position_code: str, *, require_unpositioned: bool):
    position = get_active_position(unit, position_code, project_id=beam.project_id)
    if beam.current_position_id == position.id:
        return beam
    if require_unpositioned and beam.current_position_id is not None:
        raise BeamAlreadyPositionedError("梁已有当前位置，请使用 move_beam")
    occupying_beam = get_beam_at_position(unit.session, position.id, for_update=True)
    if occupying_beam is not None and occupying_beam.id != beam.id:
        raise PositionOccupiedError(f"梁位已被占用: position_code={position_code}")
    return set_beam_position(unit.session, beam, position=position)


def release_beam(unit, beam):
    if beam.current_position_id is not None:
        set_beam_position(unit.session, beam, position=None)
    return beam
