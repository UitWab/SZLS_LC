from datetime import datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from backend_db.models import OperationAuditLog, Project


OPERATION_AUDIT_LOG_SORT_COLUMNS = {
    "id": OperationAuditLog.id,
    "action_code": OperationAuditLog.action_code,
    "resource_type": OperationAuditLog.resource_type,
    "occurred_at": OperationAuditLog.occurred_at,
    "created_at": OperationAuditLog.created_at,
}


def create_operation_audit_log(
    session: Session,
    *,
    project_id: int | None,
    actor_user_id: int | None,
    actor_name: str | None,
    action_code: str,
    resource_type: str,
    resource_code: str | None,
    result_code: str,
    request_id: str | None,
    source: str | None,
    summary: str | None,
    occurred_at: datetime,
) -> OperationAuditLog:
    audit_log = OperationAuditLog(
        project_id=project_id,
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        action_code=action_code,
        resource_type=resource_type,
        resource_code=resource_code,
        result_code=result_code,
        request_id=request_id,
        source=source,
        summary=summary,
        occurred_at=occurred_at,
    )
    session.add(audit_log)
    session.flush()
    return audit_log


def get_operation_audit_log(
    session: Session,
    audit_log_id: int,
    *,
    project_id: int | None = None,
    all_projects: bool = False,
) -> tuple[OperationAuditLog, str | None] | None:
    if all_projects and project_id is not None:
        raise ValueError("all_projects=True 时不能指定 project_id")
    statement = (
        select(OperationAuditLog, Project.project_code)
        .outerjoin(Project, Project.id == OperationAuditLog.project_id)
        .where(OperationAuditLog.id == audit_log_id)
    )
    if not all_projects:
        statement = statement.where(OperationAuditLog.project_id == project_id)
    row = session.execute(statement).one_or_none()
    return None if row is None else (row[0], row[1])


def list_operation_audit_logs(
    session: Session,
    *,
    project_id: int | None = None,
    all_projects: bool = False,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
    action_code: str | None = None,
    resource_type: str | None = None,
    resource_code: str | None = None,
    result_code: str | None = None,
    request_id: str | None = None,
    source: str | None = None,
    occurred_at_from: datetime | None = None,
    occurred_at_to: datetime | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[tuple[OperationAuditLog, str | None]], int | None, bool]:
    if all_projects and project_id is not None:
        raise ValueError("all_projects=True 时不能指定 project_id")
    if page < 1:
        raise ValueError("page 必须大于等于 1")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size 必须在 1 到 100 之间")
    try:
        sort_column = OPERATION_AUDIT_LOG_SORT_COLUMNS[sort_by]
    except KeyError as error:
        raise ValueError(f"不支持的审计日志排序字段: {sort_by}") from error
    if sort_order not in {"asc", "desc"}:
        raise ValueError("sort_order 只能是 asc 或 desc")

    conditions = []
    if not all_projects:
        conditions.append(OperationAuditLog.project_id == project_id)
    if actor_user_id is not None:
        conditions.append(OperationAuditLog.actor_user_id == actor_user_id)
    if actor_name is not None:
        conditions.append(OperationAuditLog.actor_name == actor_name)
    if action_code is not None:
        conditions.append(OperationAuditLog.action_code == action_code)
    if resource_type is not None:
        conditions.append(OperationAuditLog.resource_type == resource_type)
    if resource_code is not None:
        conditions.append(OperationAuditLog.resource_code == resource_code)
    if result_code is not None:
        conditions.append(OperationAuditLog.result_code == result_code)
    if request_id is not None:
        conditions.append(OperationAuditLog.request_id == request_id)
    if source is not None:
        conditions.append(OperationAuditLog.source == source)
    if occurred_at_from is not None:
        conditions.append(OperationAuditLog.occurred_at >= occurred_at_from)
    if occurred_at_to is not None:
        conditions.append(OperationAuditLog.occurred_at <= occurred_at_to)
    if keyword is not None:
        conditions.append(or_(
            OperationAuditLog.actor_name.contains(keyword, autoescape=True),
            OperationAuditLog.action_code.contains(keyword, autoescape=True),
            OperationAuditLog.resource_type.contains(keyword, autoescape=True),
            OperationAuditLog.resource_code.contains(keyword, autoescape=True),
            OperationAuditLog.summary.contains(keyword, autoescape=True),
        ))

    base = select(OperationAuditLog, Project.project_code).outerjoin(
        Project, Project.id == OperationAuditLog.project_id
    ).where(*conditions)
    total = None
    if include_total:
        total = session.scalar(
            select(func.count()).select_from(OperationAuditLog).outerjoin(
                Project, Project.id == OperationAuditLog.project_id
            ).where(*conditions)
        )

    direction = asc if sort_order == "asc" else desc
    order_columns = [direction(sort_column)]
    if sort_by != "id":
        order_columns.append(direction(OperationAuditLog.id))
    query_limit = page_size if include_total else page_size + 1
    rows = session.execute(
        base.order_by(*order_columns)
        .offset((page - 1) * page_size)
        .limit(query_limit)
    ).all()
    items = [(row[0], row[1]) for row in rows]
    if total is None:
        has_next = len(items) > page_size
        items = items[:page_size]
    else:
        has_next = page * page_size < total
    return items, total, has_next
