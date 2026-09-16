from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam import get_beam_by_code
from backend_db.crud.beam_process_execution import (
    get_beam_process_execution_by_code,
)
from backend_db.crud.beam_quality_inspection import (
    create_beam_quality_inspection,
    get_beam_quality_inspection_by_code,
    get_beam_quality_inspection_by_external_key,
    list_beam_quality_inspections,
    set_beam_quality_inspection_voided,
)
from backend_db.crud.identity import get_user
from backend_db.crud.process_definition import get_process_definition_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamProcessExecutionNotFoundError,
    BeamQualityInspectionNotFoundError,
    InactiveResourceError,
    ProcessDefinitionNotFoundError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    UserNotFoundError,
)
from backend_db.schemas import (
    BeamQualityInspectionCreate,
    BeamQualityInspectionFilter,
    BeamQualityInspectionItemRead,
    BeamQualityInspectionRead,
    BeamQualityInspectionSortField,
    BeamQualityInspectionSummary,
    BeamQualityInspectionVoid,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_summary(item) -> BeamQualityInspectionSummary:
    return BeamQualityInspectionSummary(
        id=item.id,
        project_code=None if item.project is None else item.project.project_code,
        inspection_code=item.inspection_code,
        beam_code=item.beam.beam_code,
        process_code=(
            None
            if item.process_definition is None
            else item.process_definition.process_code
        ),
        process_execution_code=(
            None
            if item.process_execution is None
            else item.process_execution.execution_code
        ),
        previous_inspection_code=(
            None
            if item.previous_inspection is None
            else item.previous_inspection.inspection_code
        ),
        inspection_type_code=item.inspection_type_code,
        result_code=item.result_code,
        inspected_at=item.inspected_at,
        actor_user_id=item.actor_user_id,
        actor_name=item.actor_name,
        source=item.source,
        is_voided=item.is_voided,
    )


def _to_read(item) -> BeamQualityInspectionRead:
    return BeamQualityInspectionRead(
        **_to_summary(item).model_dump(),
        external_record_id=item.external_record_id,
        summary=item.summary,
        items=[
            BeamQualityInspectionItemRead(
                id=detail.id,
                item_code=detail.item_code,
                item_name=detail.item_name,
                requirement_text=detail.requirement_text,
                observed_value=detail.observed_value,
                unit=detail.unit,
                result_code=detail.result_code,
                remark=detail.remark,
            )
            for detail in item.items
        ],
        voided_at=item.voided_at,
        voided_by_user_id=item.voided_by_user_id,
        voided_by_name=item.voided_by_name,
        void_reason=item.void_reason,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class BeamQualityInspectionService:
    """质量检查事实入口；不承担审批、放行、鉴权或梁状态推进。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def _resolve_create_values(unit: UnitOfWork, data: BeamQualityInspectionCreate):
        project = resolve_project_scope(unit, data.project_code)
        beam = get_beam_by_code(unit.session, data.beam_code)
        if beam is None or not matches_project_scope(beam.project_id, project):
            raise BeamNotFoundError(f"梁不存在: beam_code={data.beam_code}")

        execution = None
        if data.process_execution_code is not None:
            execution = get_beam_process_execution_by_code(
                unit.session, data.process_execution_code
            )
            if execution is None or not matches_project_scope(
                execution.project_id, project
            ):
                raise BeamProcessExecutionNotFoundError(
                    "关联的工序执行记录不存在"
                )
            if execution.beam_id != beam.id:
                raise ResourceConflictError("工序执行记录与质量检查不属于同一梁")

        process = None
        if data.process_code is not None:
            process = get_process_definition_by_code(
                unit.session,
                data.process_code,
                for_update=True,
            )
            allowed_project_ids = {None} if project is None else {None, project.id}
            if process is None or process.project_id not in allowed_project_ids:
                raise ProcessDefinitionNotFoundError(
                    f"工序不存在: process_code={data.process_code}"
                )
        elif execution is not None:
            process = execution.process_definition

        if execution is not None and process is not None:
            if execution.process_definition_id != process.id:
                raise ResourceConflictError("工序与关联执行记录的工序不一致")

        previous = None
        if data.previous_inspection_code is not None:
            previous = get_beam_quality_inspection_by_code(
                unit.session, data.previous_inspection_code
            )
            if previous is None or not matches_project_scope(
                previous.project_id, project
            ):
                raise BeamQualityInspectionNotFoundError("前次质量检查记录不存在")
            if previous.beam_id != beam.id:
                raise ResourceConflictError("复检记录必须属于同一梁")

        actor_name = data.actor_name
        if data.actor_user_id is not None:
            user = get_user(unit.session, data.actor_user_id)
            if user is None:
                raise UserNotFoundError(f"用户不存在: id={data.actor_user_id}")
            if actor_name is None:
                actor_name = user.display_name

        values = {
            "project_id": beam.project_id,
            "inspection_code": data.inspection_code,
            "beam_id": beam.id,
            "process_definition_id": None if process is None else process.id,
            "process_execution_id": None if execution is None else execution.id,
            "previous_inspection_id": None if previous is None else previous.id,
            "inspection_type_code": data.inspection_type_code,
            "result_code": data.result_code.value,
            "inspected_at": data.inspected_at,
            "actor_user_id": data.actor_user_id,
            "actor_name": actor_name,
            "source": data.source.value,
            "external_record_id": data.external_record_id,
            "summary": data.summary,
            "is_voided": False,
        }
        item_values = [
            {
                **detail.model_dump(exclude={"result_code"}),
                "result_code": detail.result_code.value,
            }
            for detail in sorted(data.items, key=lambda detail: detail.item_code)
        ]
        return project, process, execution, values, item_values

    @staticmethod
    def _validate_new_record_resources(project, process, execution) -> None:
        if project is not None and not project.is_active:
            raise InactiveResourceError("项目未启用")
        if process is not None and not process.is_active:
            raise InactiveResourceError("停用的工序不能新增质量检查记录")
        if execution is not None and execution.is_voided:
            raise ResourceConflictError("已作废的工序执行记录不能用于质量检查")

    @staticmethod
    def _same_business_content(item, values, item_values, data) -> bool:
        compared_fields = set(values) - {"is_voided"}
        if data.actor_name is None:
            compared_fields.discard("actor_name")
        if not all(getattr(item, name) == values[name] for name in compared_fields):
            return False
        stored_items = {
            detail.item_code: {
                "item_code": detail.item_code,
                "item_name": detail.item_name,
                "requirement_text": detail.requirement_text,
                "observed_value": detail.observed_value,
                "unit": detail.unit,
                "result_code": detail.result_code,
                "remark": detail.remark,
            }
            for detail in item.items
        }
        requested_items = {
            detail["item_code"]: detail for detail in item_values
        }
        return stored_items == requested_items

    @staticmethod
    def _find_existing(unit: UnitOfWork, data: BeamQualityInspectionCreate):
        by_code = get_beam_quality_inspection_by_code(
            unit.session, data.inspection_code
        )
        by_external = None
        if data.external_record_id is not None:
            by_external = get_beam_quality_inspection_by_external_key(
                unit.session, data.source.value, data.external_record_id
            )
        if by_code is not None and by_external is not None and by_code.id != by_external.id:
            raise ResourceConflictError("检查编码和外部幂等标识指向不同记录")
        return by_code or by_external

    def record(self, data: BeamQualityInspectionCreate) -> BeamQualityInspectionRead:
        try:
            with self._unit_of_work_factory() as unit:
                resolved = self._resolve_create_values(unit, data)
                project, process, execution, values, item_values = resolved
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(
                        existing, values, item_values, data
                    ):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的质量检查内容")
                self._validate_new_record_resources(project, process, execution)
                item = create_beam_quality_inspection(
                    unit.session, values, item_values
                )
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            return self._recover_concurrent_record(data)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def _recover_concurrent_record(
        self, data: BeamQualityInspectionCreate
    ) -> BeamQualityInspectionRead:
        try:
            with self._unit_of_work_factory() as unit:
                resolved = self._resolve_create_values(unit, data)
                project, process, execution, values, item_values = resolved
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(
                        existing, values, item_values, data
                    ):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的质量检查内容")
                self._validate_new_record_resources(project, process, execution)
                raise ResourceAlreadyExistsError(
                    f"质量检查编码已存在: {data.inspection_code}"
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        inspection_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamQualityInspectionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_quality_inspection_by_code(
                    unit.session, inspection_code
                )
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamQualityInspectionNotFoundError(
                        f"质量检查记录不存在: inspection_code={inspection_code}"
                    )
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamQualityInspectionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamQualityInspectionSortField = BeamQualityInspectionSortField.INSPECTED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[BeamQualityInspectionSummary]:
        filters = filters or BeamQualityInspectionFilter()
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        project_code = values.pop("project_code", None)
        for field in ("result_codes", "sources"):
            if field in values:
                values[field] = [value.value for value in values[field]]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_quality_inspections(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[BeamQualityInspectionSummary](
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
        inspection_code: str,
        data: BeamQualityInspectionVoid,
        *,
        project_code: str | None = None,
    ) -> BeamQualityInspectionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_quality_inspection_by_code(
                    unit.session, inspection_code, for_update=True
                )
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamQualityInspectionNotFoundError(
                        f"质量检查记录不存在: inspection_code={inspection_code}"
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
                set_beam_quality_inspection_voided(
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
