from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.process_definition import (
    create_process_definition,
    get_process_definition,
    get_process_definition_by_code,
    list_process_definitions,
    set_process_definition_active,
    update_process_definition,
)
from backend_db.crud.project import get_project_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    InactiveResourceError,
    ProcessDefinitionNotFoundError,
    ProjectNotFoundError,
    ResourceAlreadyExistsError,
)
from backend_db.schemas import (
    PageRequest,
    PageResult,
    ProcessDefinitionCreate,
    ProcessDefinitionFilter,
    ProcessDefinitionRead,
    ProcessDefinitionSortField,
    ProcessDefinitionSummary,
    ProcessDefinitionUpdate,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _to_read(item) -> ProcessDefinitionRead:
    return ProcessDefinitionRead(
        id=item.id,
        process_code=item.process_code,
        process_name=item.process_name,
        project_id=item.project_id,
        project_code=item.project.project_code if item.project is not None else None,
        sort_order=item.sort_order,
        is_active=item.is_active,
        remark=item.remark,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class ProcessDefinitionService:
    """工序基础资料入口；不包含流程编排或状态推进。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: ProcessDefinitionCreate) -> ProcessDefinitionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = None
                if data.project_code is not None:
                    project = get_project_by_code(unit.session, data.project_code)
                    if project is None:
                        raise ProjectNotFoundError(
                            f"项目不存在: project_code={data.project_code}"
                        )
                    if not project.is_active:
                        raise InactiveResourceError("停用的项目不能新增工序")
                values = data.model_dump(exclude={"project_code"})
                values["project_id"] = project.id if project is not None else None
                item = create_process_definition(unit.session, **values)
                item.project = project
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"工序编码已存在: {data.process_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        process_definition_id: int,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead:
        return self._get_one(
            process_definition_id=process_definition_id,
            project_scope_code=project_code,
        )

    def get_by_code(
        self,
        process_code: str,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead:
        return self._get_one(
            process_code=process_code,
            project_scope_code=project_code,
        )

    def _get_one(
        self,
        *,
        process_definition_id: int | None = None,
        process_code: str | None = None,
        project_scope_code: str | None = None,
    ) -> ProcessDefinitionRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = (
                    get_process_definition(unit.session, process_definition_id)
                    if process_definition_id is not None
                    else get_process_definition_by_code(unit.session, process_code or "")
                )
                project = resolve_project_scope(unit, project_scope_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    identity = (
                        f"id={process_definition_id}"
                        if process_definition_id is not None
                        else f"process_code={process_code}"
                    )
                    raise ProcessDefinitionNotFoundError(f"工序不存在: {identity}")
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: ProcessDefinitionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProcessDefinitionSortField = ProcessDefinitionSortField.SORT_ORDER,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProcessDefinitionSummary]:
        filters = filters or ProcessDefinitionFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                filter_values = filters.model_dump(exclude_none=True)
                project_code = filter_values.pop("project_code", None)
                include_global = filter_values.pop("include_global", False)
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_process_definitions(
                    unit.session,
                    **filter_values,
                    project_id=project.id if project is not None else None,
                    include_global=include_global,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[ProcessDefinitionSummary](
                    items=[ProcessDefinitionSummary(
                        id=item.id,
                        process_code=item.process_code,
                        process_name=item.process_name,
                        project_code=(
                            item.project.project_code if item.project is not None else None
                        ),
                        sort_order=item.sort_order,
                        is_active=item.is_active,
                    ) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update(
        self,
        process_definition_id: int,
        data: ProcessDefinitionUpdate,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = get_process_definition(unit.session, process_definition_id)
                project_scope = resolve_project_scope(unit, project_code)
                if item is None or not matches_project_scope(
                    item.project_id, project_scope
                ):
                    raise ProcessDefinitionNotFoundError(
                        f"工序不存在: id={process_definition_id}"
                    )
                changes = data.model_dump(exclude_unset=True, exclude={"project_code"})
                if "project_code" in data.model_fields_set:
                    project = None
                    if data.project_code is not None:
                        project = get_project_by_code(unit.session, data.project_code)
                        if project is None:
                            raise ProjectNotFoundError(
                                f"项目不存在: project_code={data.project_code}"
                            )
                        if not project.is_active:
                            raise InactiveResourceError("停用的项目不能关联工序")
                    changes["project_id"] = project.id if project is not None else None
                    item.project = project
                if changes:
                    update_process_definition(unit.session, item, changes)
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(
        self,
        process_definition_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = get_process_definition(unit.session, process_definition_id)
                project = resolve_project_scope(unit, project_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    raise ProcessDefinitionNotFoundError(
                        f"工序不存在: id={process_definition_id}"
                    )
                set_process_definition_active(unit.session, item, is_active=is_active)
                result = _to_read(item)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)
