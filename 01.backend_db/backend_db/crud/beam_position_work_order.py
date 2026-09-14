from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from backend_db.models import Beam, BeamPosition, BeamPositionWorkOrder

ACTIVE_STATUSES = ("PENDING", "IN_PROGRESS")
STATE_UPDATE_FIELDS = frozenset({"status", "started_at", "finished_at"})
SORT_COLUMNS = {
    "id": BeamPositionWorkOrder.id,
    "work_order_code": BeamPositionWorkOrder.work_order_code,
    "status": BeamPositionWorkOrder.status,
    "planned_at": BeamPositionWorkOrder.planned_at,
    "created_at": BeamPositionWorkOrder.created_at,
    "updated_at": BeamPositionWorkOrder.updated_at,
}


def _statement():
    return select(BeamPositionWorkOrder).options(
        joinedload(BeamPositionWorkOrder.project),
        joinedload(BeamPositionWorkOrder.beam),
        joinedload(BeamPositionWorkOrder.source_position),
        joinedload(BeamPositionWorkOrder.target_position),
    )


def create_beam_position_work_order(session: Session, **values) -> BeamPositionWorkOrder:
    item = BeamPositionWorkOrder(**values)
    session.add(item)
    session.flush()
    return item


def get_beam_position_work_order(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> BeamPositionWorkOrder | None:
    query = _statement().where(BeamPositionWorkOrder.id == work_order_id)
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_beam_position_work_order_by_code(
    session: Session,
    code: str,
    *,
    for_update: bool = False,
) -> BeamPositionWorkOrder | None:
    query = _statement().where(BeamPositionWorkOrder.work_order_code == code)
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_active_work_order_for_beam(
    session: Session,
    beam_id: int,
) -> BeamPositionWorkOrder | None:
    # 锁定当前读，避免 REPEATABLE-READ 复用锁梁前建立的旧快照。
    return session.scalar(
        select(BeamPositionWorkOrder).where(
            BeamPositionWorkOrder.beam_id == beam_id,
            BeamPositionWorkOrder.status.in_(ACTIVE_STATUSES),
        ).limit(1).with_for_update()
    )


def set_beam_position_work_order_state(
    session: Session,
    item: BeamPositionWorkOrder,
    changes: Mapping[str, object],
) -> BeamPositionWorkOrder:
    unsupported = set(changes) - STATE_UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新梁位工单字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def list_beam_position_work_orders(
    session: Session,
    *,
    project_id: int | None = None,
    include_global: bool = False,
    work_order_code: str | None = None,
    beam_code: str | None = None,
    order_types: list[str] | None = None,
    statuses: list[str] | None = None,
    source_position_code: str | None = None,
    target_position_code: str | None = None,
    planned_at_from: datetime | None = None,
    planned_at_to: datetime | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[BeamPositionWorkOrder], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("工单排序参数无效")
    source_position = aliased(BeamPosition)
    target_position = aliased(BeamPosition)
    conditions = []
    if project_id is None:
        conditions.append(BeamPositionWorkOrder.project_id.is_(None))
    elif include_global:
        conditions.append(
            or_(
                BeamPositionWorkOrder.project_id == project_id,
                BeamPositionWorkOrder.project_id.is_(None),
            )
        )
    else:
        conditions.append(BeamPositionWorkOrder.project_id == project_id)
    if work_order_code:
        conditions.append(
            BeamPositionWorkOrder.work_order_code == work_order_code
        )
    if beam_code:
        conditions.append(Beam.beam_code == beam_code)
    if order_types is not None:
        conditions.append(
            BeamPositionWorkOrder.order_type.in_(order_types)
            if order_types
            else false()
        )
    if statuses is not None:
        conditions.append(
            BeamPositionWorkOrder.status.in_(statuses) if statuses else false()
        )
    if source_position_code:
        conditions.append(source_position.position_code == source_position_code)
    if target_position_code:
        conditions.append(target_position.position_code == target_position_code)
    if planned_at_from:
        conditions.append(BeamPositionWorkOrder.planned_at >= planned_at_from)
    if planned_at_to:
        conditions.append(BeamPositionWorkOrder.planned_at <= planned_at_to)
    if keyword:
        conditions.append(
            or_(
                BeamPositionWorkOrder.work_order_code.contains(
                    keyword, autoescape=True
                ),
                Beam.beam_code.contains(keyword, autoescape=True),
                BeamPositionWorkOrder.remark.contains(keyword, autoescape=True),
            )
        )

    def joins(query):
        return (
            query.join(Beam, Beam.id == BeamPositionWorkOrder.beam_id)
            .outerjoin(
                source_position,
                source_position.id == BeamPositionWorkOrder.source_position_id,
            )
            .outerjoin(
                target_position,
                target_position.id == BeamPositionWorkOrder.target_position_id,
            )
        )

    base = joins(_statement()).where(*conditions)
    total = (
        session.scalar(
            joins(select(func.count()).select_from(BeamPositionWorkOrder)).where(
                *conditions
            )
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(BeamPositionWorkOrder.id))
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
