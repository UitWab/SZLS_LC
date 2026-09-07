from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from backend_db.crud.identity import get_user
from backend_db.crud.operation_audit_log import (
    create_operation_audit_log,
    get_operation_audit_log,
    list_operation_audit_logs,
)
from backend_db.crud.project import get_project_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    OperationAuditLogNotFoundError,
    InvalidDataError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from backend_db.schemas import (
    OperationAuditLogCreate,
    OperationAuditLogFilter,
    OperationAuditLogRead,
    OperationAuditLogScope,
    OperationAuditLogSortField,
    OperationAuditLogSummary,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error


def _to_summary(audit_log, project_code: str | None) -> OperationAuditLogSummary:
    return OperationAuditLogSummary(
        id=audit_log.id,
        project_code=project_code,
        actor_user_id=audit_log.actor_user_id,
        actor_name=audit_log.actor_name,
        action_code=audit_log.action_code,
        resource_type=audit_log.resource_type,
        resource_code=audit_log.resource_code,
        result_code=audit_log.result_code,
        occurred_at=audit_log.occurred_at,
    )


def _to_read(audit_log, project_code: str | None) -> OperationAuditLogRead:
    return OperationAuditLogRead(
        **_to_summary(audit_log, project_code).model_dump(),
        request_id=audit_log.request_id,
        source=audit_log.source,
        summary=audit_log.summary,
        created_at=audit_log.created_at,
    )


def _resolve_query_scope(
    unit: UnitOfWork,
    scope: OperationAuditLogScope,
    project_code: str | None,
) -> tuple[int | None, bool]:
    try:
        scope = OperationAuditLogScope(scope)
    except (TypeError, ValueError) as error:
        raise InvalidDataError(f"不支持的审计日志查询范围: {scope}") from error
    if scope == OperationAuditLogScope.PROJECT:
        if project_code is None:
            raise InvalidDataError("PROJECT 范围必须提供 project_code")
        project = get_project_by_code(unit.session, project_code)
        if project is None:
            raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
        return project.id, False
    if project_code is not None:
        raise InvalidDataError("只有 PROJECT 范围可以提供 project_code")
    return None, scope == OperationAuditLogScope.ALL


class OperationAuditLogService:
    """只追加审计记录；不判断鉴权、HTTP 结果或业务动作含义。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def record(self, data: OperationAuditLogCreate) -> OperationAuditLogRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = None
                if data.project_code is not None:
                    project = get_project_by_code(unit.session, data.project_code)
                    if project is None:
                        raise ProjectNotFoundError(
                            f"项目不存在: project_code={data.project_code}"
                        )
                actor_name = data.actor_name
                if data.actor_user_id is not None:
                    user = get_user(unit.session, data.actor_user_id)
                    if user is None:
                        raise UserNotFoundError(
                            f"用户不存在: id={data.actor_user_id}"
                        )
                    if actor_name is None:
                        actor_name = user.display_name
                audit_log = create_operation_audit_log(
                    unit.session,
                    project_id=None if project is None else project.id,
                    actor_user_id=data.actor_user_id,
                    actor_name=actor_name,
                    action_code=data.action_code,
                    resource_type=data.resource_type,
                    resource_code=data.resource_code,
                    result_code=data.result_code,
                    request_id=data.request_id,
                    source=data.source,
                    summary=data.summary,
                    occurred_at=data.occurred_at,
                )
                result = _to_read(
                    audit_log, None if project is None else project.project_code
                )
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        audit_log_id: int,
        *,
        scope: OperationAuditLogScope,
        project_code: str | None = None,
    ) -> OperationAuditLogRead:
        try:
            with self._unit_of_work_factory() as unit:
                project_id, all_projects = _resolve_query_scope(
                    unit, scope, project_code
                )
                row = get_operation_audit_log(
                    unit.session,
                    audit_log_id,
                    project_id=project_id,
                    all_projects=all_projects,
                )
                if row is None:
                    raise OperationAuditLogNotFoundError(
                        f"操作审计日志不存在: id={audit_log_id}"
                    )
                return _to_read(*row)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: OperationAuditLogFilter,
        page_request: PageRequest | None = None,
        *,
        sort_by: OperationAuditLogSortField = OperationAuditLogSortField.OCCURRED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[OperationAuditLogSummary]:
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                project_id, all_projects = _resolve_query_scope(
                    unit, filters.scope, filters.project_code
                )
                items, total, has_next = list_operation_audit_logs(
                    unit.session,
                    **filters.model_dump(
                        exclude_none=True,
                        exclude={"scope", "project_code"},
                    ),
                    project_id=project_id,
                    all_projects=all_projects,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[OperationAuditLogSummary](
                    items=[_to_summary(*item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)
