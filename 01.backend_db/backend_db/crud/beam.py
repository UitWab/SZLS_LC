from collections.abc import Mapping
from datetime import date, datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import Beam, BeamPosition, BeamType, YardArea


BEAM_SORT_COLUMNS = {
    "id": Beam.id,
    "beam_code": Beam.beam_code,
    "beam_name": Beam.beam_name,
    "status": Beam.status,
    "production_date": Beam.production_date,
    "created_at": Beam.created_at,
    "updated_at": Beam.updated_at,
}
BEAM_UPDATE_FIELDS = frozenset(
    {"beam_name", "beam_type_id", "production_date", "remark"}
)


def create_beam(
    session: Session,
    *,
    beam_code: str,
    beam_type_id: int,
    status: str,
    beam_name: str | None = None,
    production_date: date | None = None,
    remark: str | None = None,
) -> Beam:
    beam = Beam(
        beam_code=beam_code,
        beam_name=beam_name,
        beam_type_id=beam_type_id,
        current_position_id=None,
        status=status,
        production_date=production_date,
        remark=remark,
    )
    session.add(beam)
    session.flush()
    return beam


def _beam_statement():
    return select(Beam).options(
        joinedload(Beam.beam_type),
        joinedload(Beam.current_position).joinedload(BeamPosition.area),
    )


def get_beam(
    session: Session,
    beam_id: int,
    *,
    for_update: bool = False,
) -> Beam | None:
    statement = _beam_statement().where(Beam.id == beam_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_beam_by_code(
    session: Session,
    beam_code: str,
    *,
    for_update: bool = False,
) -> Beam | None:
    statement = _beam_statement().where(Beam.beam_code == beam_code)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_beams(
    session: Session,
    *,
    beam_code: str | None = None,
    beam_type_code: str | None = None,
    statuses: list[str] | None = None,
    current_position_code: str | None = None,
    area_code: str | None = None,
    is_positioned: bool | None = None,
    production_date_from: date | None = None,
    production_date_to: date | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    updated_at_from: datetime | None = None,
    updated_at_to: datetime | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[Beam], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in BEAM_SORT_COLUMNS:
        raise ValueError(f"不支持的梁排序字段: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    conditions = []
    if beam_code is not None:
        conditions.append(Beam.beam_code == beam_code)
    if beam_type_code is not None:
        conditions.append(BeamType.type_code == beam_type_code)
    if statuses is not None:
        conditions.append(Beam.status.in_(statuses) if statuses else false())
    if current_position_code is not None:
        conditions.append(BeamPosition.position_code == current_position_code)
    if area_code is not None:
        conditions.append(YardArea.area_code == area_code)
    if is_positioned is True:
        conditions.append(Beam.current_position_id.is_not(None))
    elif is_positioned is False:
        conditions.append(Beam.current_position_id.is_(None))
    if production_date_from is not None:
        conditions.append(Beam.production_date >= production_date_from)
    if production_date_to is not None:
        conditions.append(Beam.production_date <= production_date_to)
    if created_at_from is not None:
        conditions.append(Beam.created_at >= created_at_from)
    if created_at_to is not None:
        conditions.append(Beam.created_at <= created_at_to)
    if updated_at_from is not None:
        conditions.append(Beam.updated_at >= updated_at_from)
    if updated_at_to is not None:
        conditions.append(Beam.updated_at <= updated_at_to)
    if keyword is not None:
        conditions.append(
            or_(
                Beam.beam_code.contains(keyword, autoescape=True),
                Beam.beam_name.contains(keyword, autoescape=True),
            )
        )

    joins = (
        lambda statement: statement.join(Beam.beam_type)
        .outerjoin(Beam.current_position)
        .outerjoin(BeamPosition.area)
    )
    statement = joins(_beam_statement()).where(*conditions)
    count_statement = joins(select(func.count()).select_from(Beam)).where(*conditions)
    total = session.scalar(count_statement) if include_total else None
    direction = asc if sort_order == "asc" else desc
    sort_column = BEAM_SORT_COLUMNS[sort_by]
    order_columns = [direction(sort_column)]
    if sort_by != "id":
        order_columns.append(direction(Beam.id))
    query_limit = page_size if include_total else page_size + 1
    statement = statement.order_by(*order_columns).offset(
        (page - 1) * page_size
    ).limit(query_limit)
    items = list(session.scalars(statement).unique().all())
    if total is None:
        has_next = len(items) > page_size
        items = items[:page_size]
    else:
        has_next = page * page_size < total
    return items, total, has_next


def update_beam(
    session: Session,
    beam: Beam,
    changes: Mapping[str, object],
) -> Beam:
    unsupported = set(changes) - BEAM_UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新梁字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(beam, name, value)
    session.flush()
    return beam


def set_beam_status(session: Session, beam: Beam, *, status: str) -> Beam:
    beam.status = status
    session.flush()
    return beam


def set_beam_position(
    session: Session,
    beam: Beam,
    *,
    position: BeamPosition | None,
) -> Beam:
    beam.current_position = position
    session.flush()
    return beam
