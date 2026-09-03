from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from backend_db.models import BeamType


BEAM_TYPE_SORT_COLUMNS = {
    "id": BeamType.id,
    "type_code": BeamType.type_code,
    "type_name": BeamType.type_name,
    "created_at": BeamType.created_at,
    "updated_at": BeamType.updated_at,
}

BEAM_TYPE_UPDATE_FIELDS = frozenset(
    {
        "type_name",
        "length_mm",
        "width_mm",
        "height_mm",
        "weight_kg",
        "description",
    }
)


def create_beam_type(
    session: Session,
    *,
    type_code: str,
    type_name: str,
    length_mm: Decimal | None = None,
    width_mm: Decimal | None = None,
    height_mm: Decimal | None = None,
    weight_kg: Decimal | None = None,
    description: str | None = None,
    is_active: bool = True,
) -> BeamType:
    beam_type = BeamType(
        type_code=type_code,
        type_name=type_name,
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        weight_kg=weight_kg,
        description=description,
        is_active=is_active,
    )

    session.add(beam_type)
    session.flush()
    return beam_type


def get_beam_type(session: Session, beam_type_id: int) -> BeamType | None:
    return session.get(BeamType, beam_type_id)


def get_beam_type_by_code(
    session: Session,
    type_code: str,
) -> BeamType | None:
    return session.scalar(
        select(BeamType).where(BeamType.type_code == type_code)
    )


def list_beam_types(
    session: Session,
    *,
    type_code: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    length_mm_min: Decimal | None = None,
    length_mm_max: Decimal | None = None,
    width_mm_min: Decimal | None = None,
    width_mm_max: Decimal | None = None,
    height_mm_min: Decimal | None = None,
    height_mm_max: Decimal | None = None,
    weight_kg_min: Decimal | None = None,
    weight_kg_max: Decimal | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[BeamType], int | None, bool]:
    if page < 1:
        raise ValueError("page 必须大于等于 1")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size 必须在 1 到 100 之间")

    try:
        sort_column = BEAM_TYPE_SORT_COLUMNS[sort_by]
    except KeyError as error:
        raise ValueError(f"不支持的梁型排序字段: {sort_by}") from error

    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    conditions = []

    if type_code is not None:
        conditions.append(BeamType.type_code == type_code)

    if is_active is not None:
        conditions.append(BeamType.is_active == is_active)

    if keyword is not None:
        conditions.append(
            or_(
                BeamType.type_code.contains(keyword, autoescape=True),
                BeamType.type_name.contains(keyword, autoescape=True),
            )
        )

    range_filters = (
        (BeamType.length_mm, length_mm_min, length_mm_max),
        (BeamType.width_mm, width_mm_min, width_mm_max),
        (BeamType.height_mm, height_mm_min, height_mm_max),
        (BeamType.weight_kg, weight_kg_min, weight_kg_max),
    )

    for column, minimum, maximum in range_filters:
        if minimum is not None:
            conditions.append(column >= minimum)
        if maximum is not None:
            conditions.append(column <= maximum)

    statement = select(BeamType).where(*conditions)
    total = None

    if include_total:
        total = session.scalar(
            select(func.count()).select_from(BeamType).where(*conditions)
        )

    direction = asc if sort_order == "asc" else desc
    order_columns = [direction(sort_column)]

    if sort_by != "id":
        order_columns.append(direction(BeamType.id))

    query_limit = page_size if include_total else page_size + 1
    statement = statement.order_by(*order_columns).offset(
        (page - 1) * page_size
    ).limit(query_limit)

    items = list(session.scalars(statement).all())

    if total is None:
        has_next = len(items) > page_size
        items = items[:page_size]
    else:
        has_next = page * page_size < total

    return items, total, has_next


def update_beam_type(
    session: Session,
    beam_type: BeamType,
    changes: Mapping[str, object],
) -> BeamType:
    unsupported_fields = set(changes) - BEAM_TYPE_UPDATE_FIELDS

    if unsupported_fields:
        field_names = ", ".join(sorted(unsupported_fields))
        raise ValueError(f"不允许更新梁型字段: {field_names}")

    for field_name, value in changes.items():
        setattr(beam_type, field_name, value)

    session.flush()
    return beam_type


def set_beam_type_active(
    session: Session,
    beam_type: BeamType,
    *,
    is_active: bool,
) -> BeamType:
    beam_type.is_active = is_active
    session.flush()
    return beam_type
