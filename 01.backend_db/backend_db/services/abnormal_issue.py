from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.abnormal_issue import (
    create_abnormal_issue,
    get_abnormal_issue_by_code,
    get_abnormal_issue_by_external_key,
    list_abnormal_issues,
    set_abnormal_issue_state,
)
from backend_db.crud.beam import get_beam_by_code
from backend_db.crud.identity import get_user
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    AbnormalIssueNotFoundError,
    BeamNotFoundError,
    InactiveResourceError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    UserNotFoundError,
)
from backend_db.schemas import (
    AbnormalIssueActorAction,
    AbnormalIssueClose,
    AbnormalIssueCreate,
    AbnormalIssueFilter,
    AbnormalIssueRead,
    AbnormalIssueResolve,
    AbnormalIssueSortField,
    AbnormalIssueStatus,
    AbnormalIssueSummary,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_summary(item) -> AbnormalIssueSummary:
    return AbnormalIssueSummary(
        id=item.id,
        project_code=item.project.project_code,
        issue_code=item.issue_code,
        beam_code=None if item.beam is None else item.beam.beam_code,
        device_code=item.device_code,
        category_code=item.category_code,
        issue_type_code=item.issue_type_code,
        severity=item.severity,
        status=item.status,
        title=item.title,
        occurred_at=item.occurred_at,
        source=item.source,
    )


def _to_read(item) -> AbnormalIssueRead:
    return AbnormalIssueRead(
        **_to_summary(item).model_dump(),
        message=item.message,
        reported_by_user_id=item.reported_by_user_id,
        reported_by_name=item.reported_by_name,
        external_record_id=item.external_record_id,
        processing_started_at=item.processing_started_at,
        processing_by_user_id=item.processing_by_user_id,
        processing_by_name=item.processing_by_name,
        resolved_at=item.resolved_at,
        resolved_by_user_id=item.resolved_by_user_id,
        resolved_by_name=item.resolved_by_name,
        resolution_summary=item.resolution_summary,
        closed_at=item.closed_at,
        closed_by_user_id=item.closed_by_user_id,
        closed_by_name=item.closed_by_name,
        close_note=item.close_note,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class AbnormalIssueService:
    """异常事项数据用例；不判断异常、不通知，也不执行设备控制。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def _resolve_user(unit: UnitOfWork, user_id: int | None, name: str | None):
        if user_id is None:
            return name
        user = get_user(unit.session, user_id)
        if user is None:
            raise UserNotFoundError(f"用户不存在: id={user_id}")
        return name or user.display_name

    @classmethod
    def _resolve_create_values(cls, unit: UnitOfWork, data: AbnormalIssueCreate):
        project = resolve_project_scope(unit, data.project_code, for_share=True)
        if project is None:
            raise ResourceConflictError("异常事项必须属于项目")
        beam = None
        if data.beam_code is not None:
            beam = get_beam_by_code(unit.session, data.beam_code)
            if beam is None or not matches_project_scope(beam.project_id, project):
                raise BeamNotFoundError(f"梁不存在: beam_code={data.beam_code}")
        reported_by_name = cls._resolve_user(
            unit, data.reported_by_user_id, data.reported_by_name
        )
        values = {
            "project_id": project.id,
            "issue_code": data.issue_code,
            "beam_id": None if beam is None else beam.id,
            "device_code": data.device_code,
            "category_code": data.category_code.value,
            "issue_type_code": data.issue_type_code,
            "severity": data.severity.value,
            "status": AbnormalIssueStatus.OPEN.value,
            "title": data.title,
            "message": data.message,
            "occurred_at": data.occurred_at,
            "reported_by_user_id": data.reported_by_user_id,
            "reported_by_name": reported_by_name,
            "source": data.source.value,
            "external_record_id": data.external_record_id,
        }
        return project, values

    @staticmethod
    def _find_existing(unit: UnitOfWork, data: AbnormalIssueCreate):
        by_code = get_abnormal_issue_by_code(unit.session, data.issue_code)
        by_external = None
        if data.external_record_id is not None:
            by_external = get_abnormal_issue_by_external_key(
                unit.session, data.source.value, data.external_record_id
            )
        if by_code is not None and by_external is not None and by_code.id != by_external.id:
            raise ResourceConflictError("异常编码和外部幂等标识指向不同记录")
        return by_code or by_external

    @staticmethod
    def _same_business_content(item, values, data: AbnormalIssueCreate) -> bool:
        fields = set(values) - {"status"}
        if data.reported_by_name is None:
            fields.discard("reported_by_name")
        return all(getattr(item, name) == values[name] for name in fields)

    def record(self, data: AbnormalIssueCreate) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的异常事项内容")
                if not project.is_active:
                    raise InactiveResourceError("项目未启用")
                item = create_abnormal_issue(unit.session, **values)
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            return self._recover_concurrent_record(data)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def _recover_concurrent_record(
        self, data: AbnormalIssueCreate
    ) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的异常事项内容")
                if not project.is_active:
                    raise InactiveResourceError("项目未启用")
                raise ResourceAlreadyExistsError(
                    f"异常事项编码已存在: {data.issue_code}"
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, issue_code: str, *, project_code: str) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_abnormal_issue_by_code(unit.session, issue_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    raise AbnormalIssueNotFoundError(
                        f"异常事项不存在: issue_code={issue_code}"
                    )
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: AbnormalIssueFilter,
        page_request: PageRequest | None = None,
        *,
        sort_by: AbnormalIssueSortField = AbnormalIssueSortField.OCCURRED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[AbnormalIssueSummary]:
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        project_code = values.pop("project_code")
        for field in ("category_codes", "severities", "statuses", "sources"):
            if field in values:
                values[field] = [value.value for value in values[field]]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                if project is None:
                    raise ResourceConflictError("异常事项查询必须指定项目")
                items, total, has_next = list_abnormal_issues(
                    unit.session,
                    **values,
                    project_id=project.id,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[AbnormalIssueSummary](
                    items=[_to_summary(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    @classmethod
    def _action_values(cls, unit: UnitOfWork, data: AbnormalIssueActorAction):
        return data.actor_user_id, cls._resolve_user(
            unit, data.actor_user_id, data.actor_name
        )

    @staticmethod
    def _same_actor(
        stored_user_id,
        stored_name,
        data: AbnormalIssueActorAction,
        resolved_name,
    ) -> bool:
        if stored_user_id != data.actor_user_id:
            return False
        return data.actor_name is None or stored_name == resolved_name

    def start_processing(
        self,
        issue_code: str,
        data: AbnormalIssueActorAction,
        *,
        project_code: str,
    ) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = self._get_locked(unit, issue_code, project_code)
                actor_id, actor_name = self._action_values(unit, data)
                if item.processing_started_at is not None:
                    if self._same_actor(
                        item.processing_by_user_id,
                        item.processing_by_name,
                        data,
                        actor_name,
                    ):
                        return _to_read(item)
                    raise ResourceConflictError("异常事项已由其他处理人开始处理")
                if item.status != AbnormalIssueStatus.OPEN.value:
                    raise ResourceConflictError("当前异常事项状态不允许开始处理")
                set_abnormal_issue_state(
                    unit.session,
                    item,
                    {
                        "status": AbnormalIssueStatus.IN_PROGRESS.value,
                        "processing_started_at": _utc_now(),
                        "processing_by_user_id": actor_id,
                        "processing_by_name": actor_name,
                    },
                )
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def resolve(
        self,
        issue_code: str,
        data: AbnormalIssueResolve,
        *,
        project_code: str,
    ) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = self._get_locked(unit, issue_code, project_code)
                actor_id, actor_name = self._action_values(unit, data)
                if item.resolved_at is not None:
                    if self._same_actor(
                        item.resolved_by_user_id,
                        item.resolved_by_name,
                        data,
                        actor_name,
                    ) and item.resolution_summary == data.resolution_summary:
                        return _to_read(item)
                    raise ResourceConflictError("异常事项已使用不同内容解决")
                if item.status not in {
                    AbnormalIssueStatus.OPEN.value,
                    AbnormalIssueStatus.IN_PROGRESS.value,
                }:
                    raise ResourceConflictError("当前异常事项状态不允许解决")
                set_abnormal_issue_state(
                    unit.session,
                    item,
                    {
                        "status": AbnormalIssueStatus.RESOLVED.value,
                        "resolved_at": _utc_now(),
                        "resolved_by_user_id": actor_id,
                        "resolved_by_name": actor_name,
                        "resolution_summary": data.resolution_summary,
                    },
                )
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def close(
        self,
        issue_code: str,
        data: AbnormalIssueClose,
        *,
        project_code: str,
    ) -> AbnormalIssueRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = self._get_locked(unit, issue_code, project_code)
                actor_id, actor_name = self._action_values(unit, data)
                if item.closed_at is not None:
                    if self._same_actor(
                        item.closed_by_user_id,
                        item.closed_by_name,
                        data,
                        actor_name,
                    ) and item.close_note == data.close_note:
                        return _to_read(item)
                    raise ResourceConflictError("异常事项已使用不同内容关闭")
                if item.status != AbnormalIssueStatus.RESOLVED.value:
                    raise ResourceConflictError("异常事项必须先解决后关闭")
                set_abnormal_issue_state(
                    unit.session,
                    item,
                    {
                        "status": AbnormalIssueStatus.CLOSED.value,
                        "closed_at": _utc_now(),
                        "closed_by_user_id": actor_id,
                        "closed_by_name": actor_name,
                        "close_note": data.close_note,
                    },
                )
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    @staticmethod
    def _get_locked(
        unit: UnitOfWork,
        issue_code: str,
        project_code: str,
    ):
        project = resolve_project_scope(unit, project_code)
        item = get_abnormal_issue_by_code(
            unit.session, issue_code, for_update=True
        )
        if item is None or not matches_project_scope(item.project_id, project):
            raise AbnormalIssueNotFoundError(
                f"异常事项不存在: issue_code={issue_code}"
            )
        return item
