from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam_position import (
    create_beam_position,
    get_beam_at_position,
    get_beam_position,
    get_beam_position_by_code,
    list_beam_positions,
    set_beam_position_active,
    update_beam_position,
)
from backend_db.crud.yard_area import get_yard_area_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamPositionNotFoundError,
    InactiveResourceError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    YardAreaNotFoundError,
)
from backend_db.mappers import beam_position_to_read, beam_position_to_summary
from backend_db.schemas import (
    BeamPositionCreate,
    BeamPositionFilter,
    BeamPositionRead,
    BeamPositionSortField,
    BeamPositionSummary,
    BeamPositionUpdate,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


class BeamPositionService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: BeamPositionCreate) -> BeamPositionRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, data.project_code, require_active=True)
                area = self._resolve_active_area(
                    unit,
                    data.area_code,
                    project_id=project.id if project is not None else None,
                )
                values = data.model_dump(exclude={"area_code", "project_code"})
                position = create_beam_position(
                    unit.session,
                    **values,
                    area_id=area.id,
                )
                result = beam_position_to_read(position)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"梁位编码已存在: {data.position_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self, position_id: int, *, project_code: str | None = None
    ) -> BeamPositionRead:
        return self._get_one(position_id=position_id, project_code=project_code)

    def get_by_code(
        self, position_code: str, *, project_code: str | None = None
    ) -> BeamPositionRead:
        return self._get_one(position_code=position_code, project_code=project_code)

    def _get_one(
        self,
        *,
        position_id: int | None = None,
        position_code: str | None = None,
        project_code: str | None = None,
    ) -> BeamPositionRead:
        try:
            with self._unit_of_work_factory() as unit:
                position = (
                    get_beam_position(unit.session, position_id)
                    if position_id is not None
                    else get_beam_position_by_code(unit.session, position_code or "")
                )
                project = resolve_project_scope(unit, project_code)
                resource_project_id = (
                    position.area.project_id if position is not None else None
                )
                if position is None or not matches_project_scope(
                    resource_project_id, project
                ):
                    identity = (
                        f"id={position_id}"
                        if position_id is not None
                        else f"position_code={position_code}"
                    )
                    raise BeamPositionNotFoundError(f"梁位不存在: {identity}")
                return beam_position_to_read(position)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamPositionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamPositionSortField = BeamPositionSortField.POSITION_CODE,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamPositionSummary]:
        filters = filters or BeamPositionFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                filter_values = filters.model_dump(exclude_none=True)
                project_code = filter_values.pop("project_code", None)
                include_global = filter_values.pop("include_global", False)
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_positions(
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
                return PageResult[BeamPositionSummary](
                    items=[beam_position_to_summary(item) for item in items],
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
        position_id: int,
        data: BeamPositionUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamPositionRead:
        try:
            with self._unit_of_work_factory() as unit:
                position = get_beam_position(unit.session, position_id, for_update=True)
                project = resolve_project_scope(unit, project_code)
                resource_project_id = (
                    position.area.project_id if position is not None else None
                )
                if position is None or not matches_project_scope(
                    resource_project_id, project
                ):
                    raise BeamPositionNotFoundError(f"梁位不存在: id={position_id}")
                changes = data.model_dump(exclude_unset=True, exclude={"area_code"})
                if "area_code" in data.model_fields_set:
                    area = self._resolve_active_area(
                        unit,
                        data.area_code or "",
                        project_id=resource_project_id,
                    )
                    changes["area_id"] = area.id
                if changes:
                    update_beam_position(unit.session, position, changes)
                    if "area_id" in changes:
                        unit.session.expire(position, ["area"])
                result = beam_position_to_read(position)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(
        self,
        position_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> BeamPositionRead:
        try:
            with self._unit_of_work_factory() as unit:
                position = get_beam_position(unit.session, position_id, for_update=True)
                project = resolve_project_scope(unit, project_code)
                resource_project_id = (
                    position.area.project_id if position is not None else None
                )
                if position is None or not matches_project_scope(
                    resource_project_id, project
                ):
                    raise BeamPositionNotFoundError(f"梁位不存在: id={position_id}")
                if not is_active and get_beam_at_position(
                    unit.session,
                    position.id,
                    for_update=True,
                ) is not None:
                    raise ResourceConflictError("梁位正在被占用，不能停用")
                if is_active:
                    self._resolve_active_area(
                        unit,
                        position.area.area_code,
                        project_id=resource_project_id,
                    )
                set_beam_position_active(
                    unit.session,
                    position,
                    is_active=is_active,
                )
                result = beam_position_to_read(position)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    @staticmethod
    def _resolve_active_area(
        unit: UnitOfWork,
        area_code: str,
        *,
        project_id: int | None,
    ):
        area = get_yard_area_by_code(
            unit.session,
            area_code,
            for_update=True,
        )
        if area is None or area.project_id != project_id:
            raise YardAreaNotFoundError(f"区域不存在: area_code={area_code}")
        if not area.is_active:
            raise InactiveResourceError("所属区域未启用")
        return area
