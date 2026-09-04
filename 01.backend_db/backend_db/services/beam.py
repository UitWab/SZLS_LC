from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam import (
    create_beam,
    get_beam,
    get_beam_by_code,
    list_beams,
    set_beam_position,
    set_beam_status,
    update_beam,
)
from backend_db.crud.beam_position import (
    get_beam_at_position,
    get_beam_position_by_code,
)
from backend_db.crud.beam_type import get_beam_type_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamAlreadyPositionedError,
    BeamNotFoundError,
    BeamPositionNotFoundError,
    BeamTypeNotFoundError,
    InactiveResourceError,
    PositionOccupiedError,
    ResourceAlreadyExistsError,
)
from backend_db.mappers import beam_to_read, beam_to_summary
from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamPositionCommand,
    BeamRead,
    BeamSortField,
    BeamStatus,
    BeamStatusChange,
    BeamSummary,
    BeamUpdate,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error


class BeamService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: BeamCreate) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam_type = self._resolve_active_beam_type(
                    unit,
                    data.beam_type_code,
                )
                values = data.model_dump(
                    exclude={"beam_type_code"},
                    mode="python",
                )
                values["status"] = data.status.value
                beam = create_beam(
                    unit.session,
                    **values,
                    beam_type_id=beam_type.id,
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

    def get(self, beam_id: int) -> BeamRead:
        return self._get_one(beam_id=beam_id)

    def get_by_code(self, beam_code: str) -> BeamRead:
        return self._get_one(beam_code=beam_code)

    def _get_one(
        self,
        *,
        beam_id: int | None = None,
        beam_code: str | None = None,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = (
                    get_beam(unit.session, beam_id)
                    if beam_id is not None
                    else get_beam_by_code(unit.session, beam_code or "")
                )
                if beam is None:
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
        if "statuses" in filter_values:
            filter_values["statuses"] = [
                status.value for status in filters.statuses or []
            ]
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_beams(
                    unit.session,
                    **filter_values,
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

    def update(self, beam_id: int, data: BeamUpdate) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = get_beam(unit.session, beam_id, for_update=True)
                if beam is None:
                    raise BeamNotFoundError(f"梁不存在: id={beam_id}")
                changes = data.model_dump(
                    exclude_unset=True,
                    exclude={"beam_type_code"},
                )
                if "beam_type_code" in data.model_fields_set:
                    beam_type = self._resolve_active_beam_type(
                        unit,
                        data.beam_type_code or "",
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
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = self._get_locked_beam(unit, beam_code)
                set_beam_status(unit.session, beam, status=data.status.value)
                result = beam_to_read(beam)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def assign_position(
        self,
        beam_code: str,
        data: BeamPositionCommand,
    ) -> BeamRead:
        return self._place_beam(
            beam_code,
            data.position_code,
            require_unpositioned=True,
        )

    def move_beam(
        self,
        beam_code: str,
        data: BeamPositionCommand,
    ) -> BeamRead:
        return self._place_beam(
            beam_code,
            data.position_code,
            require_unpositioned=False,
        )

    def _place_beam(
        self,
        beam_code: str,
        position_code: str,
        *,
        require_unpositioned: bool,
    ) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = self._get_locked_beam(unit, beam_code)
                position = get_beam_position_by_code(
                    unit.session,
                    position_code,
                    for_update=True,
                )
                if position is None:
                    raise BeamPositionNotFoundError(
                        f"梁位不存在: position_code={position_code}"
                    )
                if not position.is_active:
                    raise InactiveResourceError("目标梁位未启用")
                if beam.current_position_id == position.id:
                    return beam_to_read(beam)
                if require_unpositioned and beam.current_position_id is not None:
                    raise BeamAlreadyPositionedError(
                        "梁已有当前位置，请使用 move_beam"
                    )
                occupying_beam = get_beam_at_position(
                    unit.session,
                    position.id,
                    for_update=True,
                )
                if occupying_beam is not None and occupying_beam.id != beam.id:
                    raise PositionOccupiedError(
                        f"梁位已被占用: position_code={position_code}"
                    )
                set_beam_position(unit.session, beam, position=position)
                result = beam_to_read(beam)
                unit.commit()
                return result
        except IntegrityError:
            raise PositionOccupiedError(
                f"梁位已被占用: position_code={position_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def release_position(self, beam_code: str) -> BeamRead:
        try:
            with self._unit_of_work_factory() as unit:
                beam = self._get_locked_beam(unit, beam_code)
                if beam.current_position_id is None:
                    return beam_to_read(beam)
                set_beam_position(unit.session, beam, position=None)
                result = beam_to_read(beam)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    @staticmethod
    def _get_locked_beam(unit: UnitOfWork, beam_code: str):
        beam = get_beam_by_code(unit.session, beam_code, for_update=True)
        if beam is None:
            raise BeamNotFoundError(f"梁不存在: beam_code={beam_code}")
        return beam

    @staticmethod
    def _resolve_active_beam_type(unit: UnitOfWork, type_code: str):
        beam_type = get_beam_type_by_code(unit.session, type_code)
        if beam_type is None:
            raise BeamTypeNotFoundError(f"梁型不存在: type_code={type_code}")
        if not beam_type.is_active:
            raise InactiveResourceError("梁型未启用")
        return beam_type
