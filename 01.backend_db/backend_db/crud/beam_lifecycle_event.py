from datetime import datetime

from sqlalchemy import asc, desc, false, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, joinedload

from backend_db.models import Beam, BeamLifecycleEvent
from backend_db.models.beam_lifecycle_event import BeamLifecycleEventStreamLock


SORT_COLUMNS = {
    "id": BeamLifecycleEvent.id,
    "event_type": BeamLifecycleEvent.event_type,
    "occurred_at": BeamLifecycleEvent.occurred_at,
    "created_at": BeamLifecycleEvent.created_at,
}


def _statement():
    return select(BeamLifecycleEvent).options(
        joinedload(BeamLifecycleEvent.project),
        joinedload(BeamLifecycleEvent.beam),
        joinedload(BeamLifecycleEvent.source_position),
        joinedload(BeamLifecycleEvent.target_position),
        joinedload(BeamLifecycleEvent.work_order),
    )


def create_beam_lifecycle_event(
    session: Session,
    **values,
) -> BeamLifecycleEvent:
    _lock_event_stream(session, values.get("project_id"))
    item = BeamLifecycleEvent(**values)
    session.add(item)
    session.flush()
    return item


def _lock_event_stream(session: Session, project_id: int | None) -> None:
    """锁定到事务结束，使同一项目的事件 ID 顺序与提交顺序一致。"""

    scope_key = "GLOBAL" if project_id is None else f"PROJECT:{project_id}"
    statement = mysql_insert(BeamLifecycleEventStreamLock).values(
        scope_key=scope_key
    )
    session.execute(
        statement.on_duplicate_key_update(scope_key=scope_key)
    )
    session.scalar(
        select(BeamLifecycleEventStreamLock.scope_key)
        .where(BeamLifecycleEventStreamLock.scope_key == scope_key)
        .with_for_update()
    )


def get_beam_lifecycle_event(
    session: Session,
    event_id: int,
    *,
    project_id: int | None,
) -> BeamLifecycleEvent | None:
    return session.scalar(
        _statement().where(
            BeamLifecycleEvent.id == event_id,
            BeamLifecycleEvent.project_id == project_id,
        )
    )


def _conditions(
    *,
    project_id: int | None,
    beam_code: str | None,
    event_types: list[str] | None,
    occurred_at_from: datetime | None,
    occurred_at_to: datetime | None,
):
    conditions = [BeamLifecycleEvent.project_id == project_id]
    if beam_code is not None:
        conditions.append(Beam.beam_code == beam_code)
    if event_types is not None:
        conditions.append(
            BeamLifecycleEvent.event_type.in_(event_types)
            if event_types
            else false()
        )
    if occurred_at_from is not None:
        conditions.append(BeamLifecycleEvent.occurred_at >= occurred_at_from)
    if occurred_at_to is not None:
        conditions.append(BeamLifecycleEvent.occurred_at <= occurred_at_to)
    return conditions


def list_beam_lifecycle_events(
    session: Session,
    *,
    project_id: int | None,
    beam_code: str | None = None,
    event_types: list[str] | None = None,
    occurred_at_from: datetime | None = None,
    occurred_at_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[BeamLifecycleEvent], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("梁生命周期事件排序参数无效")
    conditions = _conditions(
        project_id=project_id,
        beam_code=beam_code,
        event_types=event_types,
        occurred_at_from=occurred_at_from,
        occurred_at_to=occurred_at_to,
    )
    base = _statement().join(Beam, Beam.id == BeamLifecycleEvent.beam_id).where(
        *conditions
    )
    total = (
        session.scalar(
            select(func.count())
            .select_from(BeamLifecycleEvent)
            .join(Beam, Beam.id == BeamLifecycleEvent.beam_id)
            .where(*conditions)
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(BeamLifecycleEvent.id))
    limit = page_size if include_total else page_size + 1
    items = list(
        session.scalars(
            base.order_by(*order)
            .offset((page - 1) * page_size)
            .limit(limit)
        ).unique()
    )
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next


def list_beam_lifecycle_events_after(
    session: Session,
    *,
    project_id: int | None,
    beam_code: str | None = None,
    event_types: list[str] | None = None,
    occurred_at_from: datetime | None = None,
    occurred_at_to: datetime | None = None,
    after_id: int | None = None,
    limit: int = 100,
) -> tuple[list[BeamLifecycleEvent], bool]:
    if not 1 <= limit <= 100:
        raise ValueError("limit 必须在 1 到 100 之间")
    conditions = _conditions(
        project_id=project_id,
        beam_code=beam_code,
        event_types=event_types,
        occurred_at_from=occurred_at_from,
        occurred_at_to=occurred_at_to,
    )
    if after_id is not None:
        conditions.append(BeamLifecycleEvent.id > after_id)
    items = list(
        session.scalars(
            _statement()
            .join(Beam, Beam.id == BeamLifecycleEvent.beam_id)
            .where(*conditions)
            .order_by(BeamLifecycleEvent.id.asc())
            .limit(limit + 1)
        ).unique()
    )
    return items[:limit], len(items) > limit
