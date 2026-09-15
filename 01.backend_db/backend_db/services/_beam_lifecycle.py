from datetime import datetime, timezone

from backend_db.crud.beam_lifecycle_event import create_beam_lifecycle_event
from backend_db.schemas import BeamLifecycleEventType


POSITION_EVENT_TYPES = {
    BeamLifecycleEventType.POSITION_ASSIGNED,
    BeamLifecycleEventType.POSITION_MOVED,
    BeamLifecycleEventType.POSITION_RELEASED,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_shape(
    event_type: BeamLifecycleEventType,
    *,
    status_before: str | None,
    status_after: str | None,
    source_position_id: int | None,
    target_position_id: int | None,
    work_order_id: int | None,
) -> None:
    if event_type == BeamLifecycleEventType.BEAM_CREATED:
        valid = (
            status_before is None
            and status_after is not None
            and source_position_id is None
            and target_position_id is None
        )
    elif event_type == BeamLifecycleEventType.STATUS_CHANGED:
        valid = (
            status_before is not None
            and status_after is not None
            and status_before != status_after
            and source_position_id is None
            and target_position_id is None
        )
    elif event_type == BeamLifecycleEventType.POSITION_ASSIGNED:
        valid = source_position_id is None and target_position_id is not None
    elif event_type == BeamLifecycleEventType.POSITION_MOVED:
        valid = (
            source_position_id is not None
            and target_position_id is not None
            and source_position_id != target_position_id
        )
    elif event_type == BeamLifecycleEventType.POSITION_RELEASED:
        valid = source_position_id is not None and target_position_id is None
    else:
        valid = False
    if not valid:
        raise ValueError(f"梁生命周期事件字段与类型不匹配: {event_type.value}")
    if event_type in POSITION_EVENT_TYPES:
        if status_before is not None or status_after is not None:
            raise ValueError("梁位事件不能携带状态变化字段")
    elif work_order_id is not None:
        raise ValueError("只有梁位事件可以关联梁位工单")


def record_beam_lifecycle_event(
    unit,
    *,
    beam,
    event_type: BeamLifecycleEventType,
    status_before: str | None = None,
    status_after: str | None = None,
    source_position_id: int | None = None,
    target_position_id: int | None = None,
    work_order_id: int | None = None,
    occurred_at: datetime | None = None,
):
    _validate_shape(
        event_type,
        status_before=status_before,
        status_after=status_after,
        source_position_id=source_position_id,
        target_position_id=target_position_id,
        work_order_id=work_order_id,
    )
    return create_beam_lifecycle_event(
        unit.session,
        project_id=beam.project_id,
        beam_id=beam.id,
        event_type=event_type.value,
        status_before=status_before,
        status_after=status_after,
        source_position_id=source_position_id,
        target_position_id=target_position_id,
        work_order_id=work_order_id,
        occurred_at=occurred_at or _utc_now(),
    )
