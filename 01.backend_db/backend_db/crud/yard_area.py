from collections.abc import Mapping

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from backend_db.models import BeamPosition, YardArea


YARD_AREA_SORT_COLUMNS = {
    "id": YardArea.id,
    "area_code": YardArea.area_code,
    "area_name": YardArea.area_name,
    "sort_order": YardArea.sort_order,
    "created_at": YardArea.created_at,
    "updated_at": YardArea.updated_at,
}
YARD_AREA_UPDATE_FIELDS = frozenset(
    {"area_name", "area_type", "parent_id", "sort_order", "remark"}
)


def create_yard_area(
    session: Session,
    *,
    area_code: str,
    area_name: str,
    area_type: str,
    parent_id: int | None = None,
    sort_order: int = 0,
    is_active: bool = True,
    remark: str | None = None,
) -> YardArea:
    area = YardArea(
        area_code=area_code,
        area_name=area_name,
        area_type=area_type,
        parent_id=parent_id,
        sort_order=sort_order,
        is_active=is_active,
        remark=remark,
    )
    session.add(area)
    session.flush()
    return area


def get_yard_area(
    session: Session,
    area_id: int,
    *,
    for_update: bool = False,
) -> YardArea | None:
    statement = select(YardArea).options(joinedload(YardArea.parent)).where(
        YardArea.id == area_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_yard_area_by_code(
    session: Session,
    area_code: str,
    *,
    for_update: bool = False,
) -> YardArea | None:
    statement = select(YardArea).options(joinedload(YardArea.parent)).where(
        YardArea.area_code == area_code
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_yard_areas(
    session: Session,
    *,
    area_code: str | None = None,
    area_type: str | None = None,
    parent_area_code: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "sort_order",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[YardArea], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in YARD_AREA_SORT_COLUMNS:
        raise ValueError(f"不支持的区域排序字段: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    parent = aliased(YardArea)
    conditions = []
    statement = select(YardArea).options(joinedload(YardArea.parent))
    count_statement = select(func.count()).select_from(YardArea)

    if parent_area_code is not None:
        statement = statement.join(parent, YardArea.parent_id == parent.id)
        count_statement = count_statement.join(parent, YardArea.parent_id == parent.id)
        conditions.append(parent.area_code == parent_area_code)
    if area_code is not None:
        conditions.append(YardArea.area_code == area_code)
    if area_type is not None:
        conditions.append(YardArea.area_type == area_type)
    if is_active is not None:
        conditions.append(YardArea.is_active == is_active)
    if keyword is not None:
        conditions.append(
            or_(
                YardArea.area_code.contains(keyword, autoescape=True),
                YardArea.area_name.contains(keyword, autoescape=True),
            )
        )

    statement = statement.where(*conditions)
    total = session.scalar(count_statement.where(*conditions)) if include_total else None
    direction = asc if sort_order == "asc" else desc
    sort_column = YARD_AREA_SORT_COLUMNS[sort_by]
    order_columns = [direction(sort_column)]
    if sort_by != "id":
        order_columns.append(direction(YardArea.id))

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


def list_all_yard_areas(
    session: Session,
    *,
    is_active: bool | None = None,
) -> list[YardArea]:
    statement = select(YardArea).options(joinedload(YardArea.parent))
    if is_active is not None:
        statement = statement.where(YardArea.is_active == is_active)
    statement = statement.order_by(YardArea.sort_order.asc(), YardArea.id.asc())
    return list(session.scalars(statement).all())


def update_yard_area(
    session: Session,
    area: YardArea,
    changes: Mapping[str, object],
) -> YardArea:
    unsupported = set(changes) - YARD_AREA_UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新区域字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(area, name, value)
    session.flush()
    return area


def set_yard_area_active(
    session: Session,
    area: YardArea,
    *,
    is_active: bool,
) -> YardArea:
    area.is_active = is_active
    session.flush()
    return area


def has_active_child_areas(session: Session, area_id: int) -> bool:
    return bool(
        session.scalar(
            select(func.count()).select_from(YardArea).where(
                YardArea.parent_id == area_id,
                YardArea.is_active.is_(True),
            )
        )
    )


def has_active_positions(session: Session, area_id: int) -> bool:
    return bool(
        session.scalar(
            select(func.count()).select_from(BeamPosition).where(
                BeamPosition.area_id == area_id,
                BeamPosition.is_active.is_(True),
            )
        )
    )
