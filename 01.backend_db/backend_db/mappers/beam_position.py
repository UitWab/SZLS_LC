from backend_db.models import BeamPosition
from backend_db.schemas import BeamPositionRead, BeamPositionSummary


def beam_position_to_summary(position: BeamPosition) -> BeamPositionSummary:
    return BeamPositionSummary(
        id=position.id,
        position_code=position.position_code,
        position_name=position.position_name,
        area_code=position.area.area_code,
        area_name=position.area.area_name,
        is_active=position.is_active,
        is_occupied=position.current_beam is not None,
    )


def beam_position_to_read(position: BeamPosition) -> BeamPositionRead:
    return BeamPositionRead(
        **beam_position_to_summary(position).model_dump(),
        area_id=position.area_id,
        x_mm=position.x_mm,
        y_mm=position.y_mm,
        z_mm=position.z_mm,
        remark=position.remark,
        current_beam_code=(
            position.current_beam.beam_code if position.current_beam else None
        ),
        created_at=position.created_at,
        updated_at=position.updated_at,
    )
