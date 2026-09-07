from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam_type import (
    create_beam_type,
    get_beam_type,
    get_beam_type_by_code,
    list_beam_types,
    set_beam_type_active,
    update_beam_type,
)
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import BeamTypeNotFoundError, ResourceAlreadyExistsError
from backend_db.schemas import (
    BeamTypeCreate,
    BeamTypeFilter,
    BeamTypeRead,
    BeamTypeSortField,
    BeamTypeSummary,
    BeamTypeUpdate,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


UnitOfWorkFactory = Callable[[], UnitOfWork]


class BeamTypeService:
    """梁型用例入口；负责事务、异常转换和DTO边界。"""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory = UnitOfWork,
    ):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: BeamTypeCreate) -> BeamTypeRead:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                project = resolve_project_scope(
                    unit_of_work, data.project_code, require_active=True
                )
                beam_type = create_beam_type(
                    unit_of_work.session,
                    **data.model_dump(exclude={"project_code"}),
                    project_id=project.id if project is not None else None,
                )
                beam_type.project = project
                result = BeamTypeRead.model_validate(beam_type)
                unit_of_work.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"梁型编码已存在: {data.type_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, beam_type_id: int, *, project_code: str | None = None) -> BeamTypeRead:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                beam_type = get_beam_type(
                    unit_of_work.session,
                    beam_type_id,
                )
                project = resolve_project_scope(unit_of_work, project_code)

                if beam_type is None or not matches_project_scope(
                    beam_type.project_id, project
                ):
                    raise BeamTypeNotFoundError(
                        f"梁型不存在: id={beam_type_id}"
                    )

                return BeamTypeRead.model_validate(beam_type)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get_by_code(
        self, type_code: str, *, project_code: str | None = None
    ) -> BeamTypeRead:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                beam_type = get_beam_type_by_code(
                    unit_of_work.session,
                    type_code,
                )
                project = resolve_project_scope(unit_of_work, project_code)

                if beam_type is None or not matches_project_scope(
                    beam_type.project_id, project
                ):
                    raise BeamTypeNotFoundError(
                        f"梁型不存在: type_code={type_code}"
                    )

                return BeamTypeRead.model_validate(beam_type)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamTypeFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamTypeSortField = BeamTypeSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamTypeSummary]:
        filters = filters or BeamTypeFilter()
        page_request = page_request or PageRequest()

        try:
            with self._unit_of_work_factory() as unit_of_work:
                filter_values = filters.model_dump(exclude_none=True)
                project_code = filter_values.pop("project_code", None)
                include_global = filter_values.pop("include_global", False)
                project = resolve_project_scope(unit_of_work, project_code)
                items, total, has_next = list_beam_types(
                    unit_of_work.session,
                    **filter_values,
                    project_id=project.id if project is not None else None,
                    include_global=include_global,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )

                return PageResult[BeamTypeSummary](
                    items=[
                        BeamTypeSummary.model_validate(item)
                        for item in items
                    ],
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
        beam_type_id: int,
        data: BeamTypeUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamTypeRead:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                beam_type = get_beam_type(
                    unit_of_work.session,
                    beam_type_id,
                )
                project = resolve_project_scope(unit_of_work, project_code)

                if beam_type is None or not matches_project_scope(
                    beam_type.project_id, project
                ):
                    raise BeamTypeNotFoundError(
                        f"梁型不存在: id={beam_type_id}"
                    )

                changes = data.model_dump(exclude_unset=True)

                if changes:
                    update_beam_type(
                        unit_of_work.session,
                        beam_type,
                        changes,
                    )

                result = BeamTypeRead.model_validate(beam_type)
                unit_of_work.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(
        self,
        beam_type_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> BeamTypeRead:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                beam_type = get_beam_type(
                    unit_of_work.session,
                    beam_type_id,
                )
                project = resolve_project_scope(unit_of_work, project_code)

                if beam_type is None or not matches_project_scope(
                    beam_type.project_id, project
                ):
                    raise BeamTypeNotFoundError(
                        f"梁型不存在: id={beam_type_id}"
                    )

                set_beam_type_active(
                    unit_of_work.session,
                    beam_type,
                    is_active=is_active,
                )
                result = BeamTypeRead.model_validate(beam_type)
                unit_of_work.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)
