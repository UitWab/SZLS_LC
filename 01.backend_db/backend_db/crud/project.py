from collections.abc import Mapping

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from backend_db.models import Project


PROJECT_SORT_COLUMNS = {
    "id": Project.id,
    "project_code": Project.project_code,
    "project_name": Project.project_name,
    "created_at": Project.created_at,
    "updated_at": Project.updated_at,
}

PROJECT_UPDATE_FIELDS = frozenset({"project_name", "remark"})


def create_project(
    session: Session,
    *,
    project_code: str,
    project_name: str,
    is_active: bool = True,
    remark: str | None = None,
) -> Project:
    project = Project(
        project_code=project_code,
        project_name=project_name,
        is_active=is_active,
        remark=remark,
    )
    session.add(project)
    session.flush()
    return project


def get_project(session: Session, project_id: int) -> Project | None:
    return session.get(Project, project_id)


def get_project_by_code(
    session: Session,
    project_code: str,
    *,
    for_update: bool = False,
) -> Project | None:
    statement = select(Project).where(Project.project_code == project_code)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_projects(
    session: Session,
    *,
    project_code: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[Project], int | None, bool]:
    if page < 1:
        raise ValueError("page 必须大于等于 1")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size 必须在 1 到 100 之间")

    try:
        sort_column = PROJECT_SORT_COLUMNS[sort_by]
    except KeyError as error:
        raise ValueError(f"不支持的项目排序字段: {sort_by}") from error
    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    conditions = []
    if project_code is not None:
        conditions.append(Project.project_code == project_code)
    if is_active is not None:
        conditions.append(Project.is_active == is_active)
    if keyword is not None:
        conditions.append(
            or_(
                Project.project_code.contains(keyword, autoescape=True),
                Project.project_name.contains(keyword, autoescape=True),
            )
        )

    statement = select(Project).where(*conditions)
    total = None
    if include_total:
        total = session.scalar(
            select(func.count()).select_from(Project).where(*conditions)
        )

    direction = asc if sort_order == "asc" else desc
    order_columns = [direction(sort_column)]
    if sort_by != "id":
        order_columns.append(direction(Project.id))

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


def update_project(
    session: Session,
    project: Project,
    changes: Mapping[str, object],
) -> Project:
    unsupported_fields = set(changes) - PROJECT_UPDATE_FIELDS
    if unsupported_fields:
        field_names = ", ".join(sorted(unsupported_fields))
        raise ValueError(f"不允许更新项目字段: {field_names}")
    for field_name, value in changes.items():
        setattr(project, field_name, value)
    session.flush()
    return project


def set_project_active(
    session: Session,
    project: Project,
    *,
    is_active: bool,
) -> Project:
    project.is_active = is_active
    session.flush()
    return project
