from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import Beam, BeamPosition, YardArea


BEAM_POSITION_SORT_COLUMNS = {
    "id": BeamPosition.id,
    "position_code": BeamPosition.position_code,
    "position_name": BeamPosition.position_name,
    "created_at": BeamPosition.created_at,
    "updated_at": BeamPosition.updated_at,
}
BEAM_POSITION_UPDATE_FIELDS = frozenset(
    {"position_name", "area_id", "x_mm", "y_mm", "z_mm", "remark"}
)


def create_beam_position(
    session: Session,
    *,
    position_code: str,
    area_id: int,
    position_name: str | None = None,
    x_mm: Decimal | None = None,
    y_mm: Decimal | None = None,
    z_mm: Decimal | None = None,
    is_active: bool = True,
    remark: str | None = None,
) -> BeamPosition:
    position = BeamPosition(
        position_code=position_code,
        position_name=position_name,
        area_id=area_id,
        x_mm=x_mm,
        y_mm=y_mm,
        z_mm=z_mm,
        is_active=is_active,
        remark=remark,
    )
    session.add(position)
    session.flush()
    return position


def _position_statement():
    return select(BeamPosition).options(
        joinedload(BeamPosition.area),
        joinedload(BeamPosition.current_beam),
    )


def get_beam_position(
    session: Session,
    position_id: int,
    *,
    for_update: bool = False,
) -> BeamPosition | None:
    statement = _position_statement().where(BeamPosition.id == position_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_beam_position_by_code(
    session: Session,
    position_code: str,
    *,
    for_update: bool = False,
) -> BeamPosition | None:
    statement = _position_statement().where(
        BeamPosition.position_code == position_code
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_beam_positions(
    session: Session,
    *,
    position_code: str | None = None,
    area_code: str | None = None,
    is_active: bool | None = None,
    is_occupied: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "position_code",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[BeamPosition], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in BEAM_POSITION_SORT_COLUMNS:
        raise ValueError(f"不支持的梁位排序字段: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    conditions = []
    if position_code is not None:
        conditions.append(BeamPosition.position_code == position_code)
    if area_code is not None:
        conditions.append(YardArea.area_code == area_code)
    if is_active is not None:
        conditions.append(BeamPosition.is_active == is_active)
    if is_occupied is True:
        conditions.append(Beam.id.is_not(None))
    elif is_occupied is False:
        conditions.append(Beam.id.is_(None))
    if keyword is not None:
        conditions.append(
            or_(
                BeamPosition.position_code.contains(keyword, autoescape=True),
                BeamPosition.position_name.contains(keyword, autoescape=True),
            )
        )

    statement = _position_statement().join(BeamPosition.area).outerjoin(
        Beam,
        Beam.current_position_id == BeamPosition.id,
    ).where(*conditions)
    count_statement = select(func.count()).select_from(BeamPosition).join(
        BeamPosition.area
    ).outerjoin(Beam, Beam.current_position_id == BeamPosition.id).where(*conditions)
    total = session.scalar(count_statement) if include_total else None
    direction = asc if sort_order == "asc" else desc
    sort_column = BEAM_POSITION_SORT_COLUMNS[sort_by]
    order_columns = [direction(sort_column)]
    if sort_by != "id":
        order_columns.append(direction(BeamPosition.id))
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


def update_beam_position(
    session: Session,
    position: BeamPosition,
    changes: Mapping[str, object],
) -> BeamPosition:
    unsupported = set(changes) - BEAM_POSITION_UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新梁位字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(position, name, value)
    session.flush()
    return position


def set_beam_position_active(
    session: Session,
    position: BeamPosition,
    *,
    is_active: bool,
) -> BeamPosition:
    position.is_active = is_active
    session.flush()
    return position


def get_beam_at_position(
    session: Session,
    position_id: int,
    *,
    for_update: bool = False,
) -> Beam | None:
    statement = select(Beam).where(Beam.current_position_id == position_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)
