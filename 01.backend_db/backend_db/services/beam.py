from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam import (
    create_beam,
    get_beam,
    get_beam_by_code,
    list_beams,
    set_beam_status,
    update_beam,
)
from backend_db.crud.beam_type import get_beam_type_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamTypeNotFoundError,
    InactiveResourceError,
    PositionOccupiedError,
    ResourceAlreadyExistsError,
)
from backend_db.mappers import beam_to_read, beam_to_summary
from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamLifecycleEventType,
    BeamPositionCommand,
    BeamRead,
    BeamSortField,
    BeamStatusChange,
    BeamSummary,
    BeamUpdate,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._beam_lifecycle import record_beam_lifecycle_event
from backend_db.services._beam_positioning import (
    get_locked_beam,
    place_beam,
    release_beam,
)
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


class BeamService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: BeamCreate) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, data.project_code, require_active=True)
                beam_type = self._resolve_active_beam_type(
                    unit,
                    data.beam_type_code,
                    project_id=project.id if project is not None else None,
                )
                values = data.model_dump(
                    exclude={"beam_type_code", "project_code"},
                    mode="python",
                )
                values["status"] = data.status.value
                beam = create_beam(
                    unit.session,
                    **values,
                    beam_type_id=beam_type.id,
                    project_id=project.id if project is not None else None,
                )
                beam.project = project
                record_beam_lifecycle_event(
                    unit,
                    beam=beam,
                    event_type=BeamLifecycleEventType.BEAM_CREATED,
                    status_after=beam.status,
                )
                result = beam_to_read(beam)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"梁编码已存在: {data.beam_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, beam_id: int, *, project_code: str | None = None) -> BeamRead:
        return self._get_one(beam_id=beam_id, project_code=project_code)

    def get_by_code(
        self, beam_code: str, *, project_code: str | None = None
    ) -> BeamRead:
        return self._get_one(beam_code=beam_code, project_code=project_code)

    def _get_one(
        self,
        *,
        beam_id: int | None = None,
        beam_code: str | None = None,
        project_code: str | None = None,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = (
                    get_beam(unit.session, beam_id)
                    if beam_id is not None
                    else get_beam_by_code(unit.session, beam_code or "")
                )
                project = resolve_project_scope(unit, project_code)
                if beam is None or not matches_project_scope(beam.project_id, project):
                    identity = (
                        f"id={beam_id}"
                        if beam_id is not None
                        else f"beam_code={beam_code}"
                    )
                    raise BeamNotFoundError(f"梁不存在: {identity}")
                return beam_to_read(beam)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamSortField = BeamSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamSummary]:
        filters = filters or BeamFilter()
        page_request = page_request or PageRequest()
        filter_values = filters.model_dump(exclude_none=True, mode="python")
        project_code = filter_values.pop("project_code", None)
        include_global = filter_values.pop("include_global", False)
        if "statuses" in filter_values:
            filter_values["statuses"] = [
                status.value for status in filters.statuses or []
            ]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beams(
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
                return PageResult[BeamSummary](
                    items=[beam_to_summary(item) for item in items],
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
        beam_id: int,
        data: BeamUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = get_beam(unit.session, beam_id, for_update=True)
                project = resolve_project_scope(unit, project_code)
                if beam is None or not matches_project_scope(beam.project_id, project):
                    raise BeamNotFoundError(f"梁不存在: id={beam_id}")
                changes = data.model_dump(
                    exclude_unset=True,
                    exclude={"beam_type_code"},
                )
                if "beam_type_code" in data.model_fields_set:
                    beam_type = self._resolve_active_beam_type(
                        unit,
                        data.beam_type_code or "",
                        project_id=beam.project_id,
                    )
                    changes["beam_type_id"] = beam_type.id
                if changes:
                    update_beam(unit.session, beam, changes)
                    if "beam_type_id" in changes:
                        unit.session.expire(beam, ["beam_type"])
                result = beam_to_read(beam)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def change_status(
        self,
        beam_code: str,
        data: BeamStatusChange,
        *,
        project_code: str | None = None,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                beam = get_locked_beam(unit, beam_code, project=project)
                status_before = beam.status
                if status_before != data.status.value:
                    set_beam_status(unit.session, beam, status=data.status.value)
                    record_beam_lifecycle_event(
                        unit,
                        beam=beam,
                        event_type=BeamLifecycleEventType.STATUS_CHANGED,
                        status_before=status_before,
                        status_after=beam.status,
                    )
                result = beam_to_read(beam)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def assign_position(
        self,
        beam_code: str,
        data: BeamPositionCommand,
        *,
        project_code: str | None = None,
    ) -> BeamRead:
        return self._place_beam(
            beam_code,
            data.position_code,
            require_unpositioned=True,
            project_code=project_code,
        )

    def move_beam(
        self,
        beam_code: str,
        data: BeamPositionCommand,
        *,
        project_code: str | None = None,
    ) -> BeamRead:
        return self._place_beam(
            beam_code,
            data.position_code,
            require_unpositioned=False,
            project_code=project_code,
        )

    def _place_beam(
        self,
        beam_code: str,
        position_code: str,
        *,
        require_unpositioned: bool,
        project_code: str | None,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                beam = get_locked_beam(unit, beam_code, project=project)
                source_position_id = beam.current_position_id
                place_beam(
                    unit, beam, position_code,
                    require_unpositioned=require_unpositioned,
                )
                if source_position_id != beam.current_position_id:
                    event_type = (
                        BeamLifecycleEventType.POSITION_ASSIGNED
                        if source_position_id is None
                        else BeamLifecycleEventType.POSITION_MOVED
                    )
                    record_beam_lifecycle_event(
                        unit,
                        beam=beam,
                        event_type=event_type,
                        source_position_id=source_position_id,
                        target_position_id=beam.current_position_id,
                    )
                result = beam_to_read(beam)
                unit.commit()
                return result
        except IntegrityError:
            raise PositionOccupiedError(
                f"梁位已被占用: position_code={position_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def release_position(
        self, beam_code: str, *, project_code: str | None = None
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                beam = get_locked_beam(unit, beam_code, project=project)
                source_position_id = beam.current_position_id
                release_beam(unit, beam)
                if source_position_id is not None:
                    record_beam_lifecycle_event(
                        unit,
                        beam=beam,
                        event_type=BeamLifecycleEventType.POSITION_RELEASED,
                        source_position_id=source_position_id,
                    )
                result = beam_to_read(beam)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    @staticmethod
    def _resolve_active_beam_type(
        unit: UnitOfWork,
        type_code: str,
        *,
        project_id: int | None,
    ):
        beam_type = get_beam_type_by_code(unit.session, type_code)
        if beam_type is None or beam_type.project_id != project_id:
            raise BeamTypeNotFoundError(f"梁型不存在: type_code={type_code}")
        if not beam_type.is_active:
            raise InactiveResourceError("梁型未启用")
        return beam_type
