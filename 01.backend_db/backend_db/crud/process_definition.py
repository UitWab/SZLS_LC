from collections.abc import Mapping

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import ProcessDefinition


SORT_COLUMNS = {
    "id": ProcessDefinition.id,
    "process_code": ProcessDefinition.process_code,
    "process_name": ProcessDefinition.process_name,
    "sort_order": ProcessDefinition.sort_order,
    "created_at": ProcessDefinition.created_at,
    "updated_at": ProcessDefinition.updated_at,
}
UPDATE_FIELDS = frozenset({"process_name", "project_id", "sort_order", "remark"})


def create_process_definition(session: Session, **values) -> ProcessDefinition:
    item = ProcessDefinition(**values)
    session.add(item)
    session.flush()
    return item


def get_process_definition(
    session: Session, process_definition_id: int
) -> ProcessDefinition | None:
    return session.scalar(
        select(ProcessDefinition)
        .options(joinedload(ProcessDefinition.project))
        .where(ProcessDefinition.id == process_definition_id)
    )


def get_process_definition_by_code(
    session: Session, process_code: str
) -> ProcessDefinition | None:
    return session.scalar(
        select(ProcessDefinition)
        .options(joinedload(ProcessDefinition.project))
        .where(ProcessDefinition.process_code == process_code)
    )


def list_process_definitions(
    session: Session,
    *,
    process_code: str | None = None,
    project_id: int | None = None,
    include_global: bool = False,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "sort_order",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[ProcessDefinition], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数不合法")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("工序排序参数不合法")

    conditions = []
    if process_code is not None:
        conditions.append(ProcessDefinition.process_code == process_code)
    if project_id is None:
        conditions.append(ProcessDefinition.project_id.is_(None))
    elif include_global:
        conditions.append(or_(
            ProcessDefinition.project_id == project_id,
            ProcessDefinition.project_id.is_(None),
        ))
    else:
        conditions.append(ProcessDefinition.project_id == project_id)
    if is_active is not None:
        conditions.append(ProcessDefinition.is_active == is_active)
    if keyword is not None:
        conditions.append(or_(
            ProcessDefinition.process_code.contains(keyword, autoescape=True),
            ProcessDefinition.process_name.contains(keyword, autoescape=True),
        ))

    base = select(ProcessDefinition).where(*conditions)
    total = None
    if include_total:
        total = session.scalar(
            select(func.count()).select_from(ProcessDefinition)
            .where(*conditions)
        )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(ProcessDefinition.id))
    limit = page_size if include_total else page_size + 1
    items = list(session.scalars(
        base.options(joinedload(ProcessDefinition.project))
        .order_by(*order).offset((page - 1) * page_size).limit(limit)
    ).all())
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next


def update_process_definition(
    session: Session,
    item: ProcessDefinition,
    changes: Mapping[str, object],
) -> ProcessDefinition:
    unsupported = set(changes) - UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新工序字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def set_process_definition_active(
    session: Session,
    item: ProcessDefinition,
    *,
    is_active: bool,
) -> ProcessDefinition:
    item.is_active = is_active
    session.flush()
    return item
