from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam import get_beam_by_code
from backend_db.crud.beam_process_execution import (
    create_beam_process_execution,
    get_beam_process_execution_by_code,
    get_beam_process_execution_by_external_key,
    list_beam_process_executions,
    set_beam_process_execution_voided,
)
from backend_db.crud.identity import get_user
from backend_db.crud.process_definition import get_process_definition_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamProcessExecutionNotFoundError,
    InactiveResourceError,
    ProcessDefinitionNotFoundError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    UserNotFoundError,
)
from backend_db.schemas import (
    BeamProcessExecutionCreate,
    BeamProcessExecutionFilter,
    BeamProcessExecutionRead,
    BeamProcessExecutionSortField,
    BeamProcessExecutionSummary,
    BeamProcessExecutionVoid,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_summary(item) -> BeamProcessExecutionSummary:
    return BeamProcessExecutionSummary(
        id=item.id,
        project_code=None if item.project is None else item.project.project_code,
        execution_code=item.execution_code,
        beam_code=item.beam.beam_code,
        process_code=item.process_definition.process_code,
        result_code=item.result_code,
        started_at=item.started_at,
        finished_at=item.finished_at,
        actor_user_id=item.actor_user_id,
        actor_name=item.actor_name,
        source=item.source,
        is_voided=item.is_voided,
    )


def _to_read(item) -> BeamProcessExecutionRead:
    return BeamProcessExecutionRead(
        **_to_summary(item).model_dump(),
        external_record_id=item.external_record_id,
        supersedes_execution_code=(
            None
            if item.supersedes_execution is None
            else item.supersedes_execution.execution_code
        ),
        remark=item.remark,
        voided_at=item.voided_at,
        voided_by_user_id=item.voided_by_user_id,
        voided_by_name=item.voided_by_name,
        void_reason=item.void_reason,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class BeamProcessExecutionService:
    """工序执行事实入口；不承担排程、鉴权或梁状态推进。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def _resolve_create_values(unit: UnitOfWork, data: BeamProcessExecutionCreate):
        project = resolve_project_scope(unit, data.project_code)
        beam = get_beam_by_code(unit.session, data.beam_code)
        if beam is None or not matches_project_scope(beam.project_id, project):
            raise BeamNotFoundError(f"梁不存在: beam_code={data.beam_code}")

        process = get_process_definition_by_code(
            unit.session,
            data.process_code,
            for_update=True,
        )
        allowed_process_project_ids = (
            {None} if project is None else {None, project.id}
        )
        if process is None or process.project_id not in allowed_process_project_ids:
            raise ProcessDefinitionNotFoundError(
                f"工序不存在: process_code={data.process_code}"
            )
        actor_name = data.actor_name
        if data.actor_user_id is not None:
            user = get_user(unit.session, data.actor_user_id)
            if user is None:
                raise UserNotFoundError(f"用户不存在: id={data.actor_user_id}")
            if actor_name is None:
                actor_name = user.display_name

        supersedes = None
        if data.supersedes_execution_code is not None:
            supersedes = get_beam_process_execution_by_code(
                unit.session, data.supersedes_execution_code
            )
            if supersedes is None or not matches_project_scope(
                supersedes.project_id, project
            ):
                raise BeamProcessExecutionNotFoundError("被替代的工序执行记录不存在")
            if (
                supersedes.beam_id != beam.id
                or supersedes.process_definition_id != process.id
            ):
                raise ResourceConflictError("替代记录必须属于同一梁和同一道工序")
            if not supersedes.is_voided:
                raise ResourceConflictError("被替代记录必须先作废")

        values = {
            "project_id": beam.project_id,
            "execution_code": data.execution_code,
            "beam_id": beam.id,
            "process_definition_id": process.id,
            "result_code": data.result_code.value,
            "started_at": data.started_at,
            "finished_at": data.finished_at,
            "actor_user_id": data.actor_user_id,
            "actor_name": actor_name,
            "source": data.source.value,
            "external_record_id": data.external_record_id,
            "supersedes_execution_id": None if supersedes is None else supersedes.id,
            "remark": data.remark,
            "is_voided": False,
        }
        return project, process, values

    @staticmethod
    def _validate_new_record_resources(project, process) -> None:
        if project is not None and not project.is_active:
            raise InactiveResourceError("项目未启用")
        if not process.is_active:
            raise InactiveResourceError("停用的工序不能新增执行记录")

    @staticmethod
    def _same_business_content(
        item,
        values: dict[str, object],
        data: BeamProcessExecutionCreate,
    ) -> bool:
        compared_fields = set(values) - {"is_voided"}
        # 未显式提供的名称是创建时快照；用户改名不改变原请求的业务含义。
        if data.actor_name is None:
            compared_fields.discard("actor_name")
        return all(
            getattr(item, name) == values[name] for name in compared_fields
        )

    @staticmethod
    def _find_existing(unit: UnitOfWork, data: BeamProcessExecutionCreate):
        by_code = get_beam_process_execution_by_code(
            unit.session, data.execution_code
        )
        by_external = None
        if data.external_record_id is not None:
            by_external = get_beam_process_execution_by_external_key(
                unit.session, data.source.value, data.external_record_id
            )
        if by_code is not None and by_external is not None and by_code.id != by_external.id:
            raise ResourceConflictError("执行编码和外部幂等标识指向不同记录")
        return by_code or by_external

    def record(self, data: BeamProcessExecutionCreate) -> BeamProcessExecutionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, process, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的工序执行内容")
                self._validate_new_record_resources(project, process)
                item = create_beam_process_execution(unit.session, **values)
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            return self._recover_concurrent_record(data)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def _recover_concurrent_record(
        self, data: BeamProcessExecutionCreate
    ) -> BeamProcessExecutionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, process, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的工序执行内容")
                self._validate_new_record_resources(project, process)
                if data.supersedes_execution_code is not None:
                    raise ResourceConflictError("被替代记录已经存在直接替代记录")
                raise ResourceAlreadyExistsError(
                    f"工序执行编码已存在: {data.execution_code}"
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        execution_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamProcessExecutionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_process_execution_by_code(unit.session, execution_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamProcessExecutionNotFoundError(
                        f"工序执行记录不存在: execution_code={execution_code}"
                    )
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamProcessExecutionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamProcessExecutionSortField = BeamProcessExecutionSortField.FINISHED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[BeamProcessExecutionSummary]:
        filters = filters or BeamProcessExecutionFilter()
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        project_code = values.pop("project_code", None)
        for field in ("result_codes", "sources"):
            if field in values:
                values[field] = [value.value for value in values[field]]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_process_executions(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[BeamProcessExecutionSummary](
                    items=[_to_summary(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def void(
        self,
        execution_code: str,
        data: BeamProcessExecutionVoid,
        *,
        project_code: str | None = None,
    ) -> BeamProcessExecutionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_process_execution_by_code(
                    unit.session, execution_code, for_update=True
                )
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamProcessExecutionNotFoundError(
                        f"工序执行记录不存在: execution_code={execution_code}"
                    )
                if item.is_voided:
                    return _to_read(item)

                voided_by_name = data.voided_by_name
                if data.voided_by_user_id is not None:
                    user = get_user(unit.session, data.voided_by_user_id)
                    if user is None:
                        raise UserNotFoundError(
                            f"用户不存在: id={data.voided_by_user_id}"
                        )
                    if voided_by_name is None:
                        voided_by_name = user.display_name
                set_beam_process_execution_voided(
                    unit.session,
                    item,
                    {
                        "is_voided": True,
                        "voided_at": _utc_now(),
                        "voided_by_user_id": data.voided_by_user_id,
                        "voided_by_name": voided_by_name,
                        "void_reason": data.void_reason,
                    },
                )
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)
