from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import Beam, BeamTransportHandover


SORT_COLUMNS = {
    "id": BeamTransportHandover.id,
    "handover_code": BeamTransportHandover.handover_code,
    "handover_type": BeamTransportHandover.handover_type,
    "result_code": BeamTransportHandover.result_code,
    "occurred_at": BeamTransportHandover.occurred_at,
    "created_at": BeamTransportHandover.created_at,
}
VOID_FIELDS = frozenset(
    {
        "is_voided",
        "voided_at",
        "voided_by_user_id",
        "voided_by_name",
        "void_reason",
    }
)


def _statement():
    return select(BeamTransportHandover).options(
        joinedload(BeamTransportHandover.project),
        joinedload(BeamTransportHandover.beam),
    )


def create_beam_transport_handover(
    session: Session,
    values: Mapping[str, object],
) -> BeamTransportHandover:
    item = BeamTransportHandover(**values)
    session.add(item)
    session.flush()
    return item


def get_beam_transport_handover_by_code(
    session: Session,
    handover_code: str,
    *,
    for_update: bool = False,
) -> BeamTransportHandover | None:
    query = _statement().where(
        BeamTransportHandover.handover_code == handover_code
    )
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_beam_transport_handover_by_external_key(
    session: Session,
    source: str,
    external_record_id: str,
) -> BeamTransportHandover | None:
    return session.scalar(
        _statement().where(
            BeamTransportHandover.source == source,
            BeamTransportHandover.external_record_id == external_record_id,
        )
    )


def set_beam_transport_handover_voided(
    session: Session,
    item: BeamTransportHandover,
    changes: Mapping[str, object],
) -> BeamTransportHandover:
    unsupported = set(changes) - VOID_FIELDS
    if unsupported:
        raise ValueError(
            f"不允许更新运输交接记录字段: {', '.join(sorted(unsupported))}"
        )
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def list_beam_transport_handovers(
    session: Session,
    *,
    project_id: int | None = None,
    handover_code: str | None = None,
    beam_code: str | None = None,
    handover_types: list[str] | None = None,
    result_codes: list[str] | None = None,
    sources: list[str] | None = None,
    occurred_at_from: datetime | None = None,
    occurred_at_to: datetime | None = None,
    vehicle_no: str | None = None,
    carrier_name: str | None = None,
    actor_user_id: int | None = None,
    external_record_id: str | None = None,
    is_voided: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[BeamTransportHandover], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("运输交接记录分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("运输交接记录排序参数无效")

    conditions = [
        BeamTransportHandover.project_id.is_(None)
        if project_id is None
        else BeamTransportHandover.project_id == project_id
    ]
    if handover_code is not None:
        conditions.append(BeamTransportHandover.handover_code == handover_code)
    if beam_code is not None:
        conditions.append(Beam.beam_code == beam_code)
    if handover_types is not None:
        conditions.append(
            BeamTransportHandover.handover_type.in_(handover_types)
            if handover_types
            else false()
        )
    if result_codes is not None:
        conditions.append(
            BeamTransportHandover.result_code.in_(result_codes)
            if result_codes
            else false()
        )
    if sources is not None:
        conditions.append(
            BeamTransportHandover.source.in_(sources) if sources else false()
        )
    if occurred_at_from is not None:
        conditions.append(BeamTransportHandover.occurred_at >= occurred_at_from)
    if occurred_at_to is not None:
        conditions.append(BeamTransportHandover.occurred_at <= occurred_at_to)
    if vehicle_no is not None:
        conditions.append(BeamTransportHandover.vehicle_no == vehicle_no)
    if carrier_name is not None:
        conditions.append(BeamTransportHandover.carrier_name == carrier_name)
    if actor_user_id is not None:
        conditions.append(BeamTransportHandover.actor_user_id == actor_user_id)
    if external_record_id is not None:
        conditions.append(
            BeamTransportHandover.external_record_id == external_record_id
        )
    if is_voided is not None:
        conditions.append(BeamTransportHandover.is_voided == is_voided)
    if keyword is not None:
        conditions.append(
            or_(
                BeamTransportHandover.handover_code.contains(
                    keyword, autoescape=True
                ),
                Beam.beam_code.contains(keyword, autoescape=True),
                BeamTransportHandover.from_location.contains(
                    keyword, autoescape=True
                ),
                BeamTransportHandover.to_location.contains(
                    keyword, autoescape=True
                ),
                BeamTransportHandover.vehicle_no.contains(keyword, autoescape=True),
                BeamTransportHandover.carrier_name.contains(
                    keyword, autoescape=True
                ),
                BeamTransportHandover.sender_name.contains(keyword, autoescape=True),
                BeamTransportHandover.receiver_name.contains(
                    keyword, autoescape=True
                ),
                BeamTransportHandover.actor_name.contains(keyword, autoescape=True),
                BeamTransportHandover.remark.contains(keyword, autoescape=True),
            )
        )

    def joins(statement):
        return statement.join(Beam, Beam.id == BeamTransportHandover.beam_id)

    base = joins(_statement()).where(*conditions)
    total = (
        session.scalar(
            joins(select(func.count()).select_from(BeamTransportHandover)).where(
                *conditions
            )
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(BeamTransportHandover.id))
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
