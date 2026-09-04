from backend_db.models import Beam
from backend_db.schemas import BeamRead, BeamStatus, BeamSummary


def beam_to_summary(beam: Beam) -> BeamSummary:
    position = beam.current_position
    return BeamSummary(
        id=beam.id,
        beam_code=beam.beam_code,
        beam_name=beam.beam_name,
        beam_type_code=beam.beam_type.type_code,
        beam_type_name=beam.beam_type.type_name,
        status=BeamStatus(beam.status),
        current_position_code=position.position_code if position else None,
        is_positioned=position is not None,
    )


def beam_to_read(beam: Beam) -> BeamRead:
    position = beam.current_position
    area = position.area if position else None
    return BeamRead(
        **beam_to_summary(beam).model_dump(),
        beam_type_id=beam.beam_type_id,
        current_position_id=beam.current_position_id,
        current_position_name=position.position_name if position else None,
        current_area_code=area.area_code if area else None,
        current_area_name=area.area_name if area else None,
        production_date=beam.production_date,
        remark=beam.remark,
        created_at=beam.created_at,
        updated_at=beam.updated_at,
    )
