from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam import get_beam_by_code
from backend_db.crud.beam_transport_handover import (
    create_beam_transport_handover,
    get_beam_transport_handover_by_code,
    get_beam_transport_handover_by_external_key,
    list_beam_transport_handovers,
    set_beam_transport_handover_voided,
)
from backend_db.crud.identity import get_user
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamTransportHandoverNotFoundError,
    InactiveResourceError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    UserNotFoundError,
)
from backend_db.schemas import (
    BeamTransportHandoverCreate,
    BeamTransportHandoverFilter,
    BeamTransportHandoverRead,
    BeamTransportHandoverSortField,
    BeamTransportHandoverSummary,
    BeamTransportHandoverVoid,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_summary(item) -> BeamTransportHandoverSummary:
    return BeamTransportHandoverSummary(
        id=item.id,
        project_code=None if item.project is None else item.project.project_code,
        handover_code=item.handover_code,
        beam_code=item.beam.beam_code,
        handover_type=item.handover_type,
        result_code=item.result_code,
        from_location=item.from_location,
        to_location=item.to_location,
        carrier_name=item.carrier_name,
        vehicle_no=item.vehicle_no,
        occurred_at=item.occurred_at,
        actor_user_id=item.actor_user_id,
        actor_name=item.actor_name,
        source=item.source,
        is_voided=item.is_voided,
    )


def _to_read(item) -> BeamTransportHandoverRead:
    return BeamTransportHandoverRead(
        **_to_summary(item).model_dump(),
        sender_name=item.sender_name,
        receiver_name=item.receiver_name,
        external_record_id=item.external_record_id,
        remark=item.remark,
        voided_at=item.voided_at,
        voided_by_user_id=item.voided_by_user_id,
        voided_by_name=item.voided_by_name,
        void_reason=item.void_reason,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class BeamTransportHandoverService:
    """运输交接事实入口；不承担调度、鉴权或梁状态推进。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def _resolve_create_values(unit: UnitOfWork, data: BeamTransportHandoverCreate):
        project = resolve_project_scope(unit, data.project_code)
        beam = get_beam_by_code(unit.session, data.beam_code)
        if beam is None or not matches_project_scope(beam.project_id, project):
            raise BeamNotFoundError(f"梁不存在: beam_code={data.beam_code}")

        actor_name = data.actor_name
        if data.actor_user_id is not None:
            user = get_user(unit.session, data.actor_user_id)
            if user is None:
                raise UserNotFoundError(f"用户不存在: id={data.actor_user_id}")
            if actor_name is None:
                actor_name = user.display_name

        values = {
            "project_id": beam.project_id,
            "handover_code": data.handover_code,
            "beam_id": beam.id,
            "handover_type": data.handover_type.value,
            "result_code": data.result_code.value,
            "from_location": data.from_location,
            "to_location": data.to_location,
            "carrier_name": data.carrier_name,
            "vehicle_no": data.vehicle_no,
            "sender_name": data.sender_name,
            "receiver_name": data.receiver_name,
            "occurred_at": data.occurred_at,
            "actor_user_id": data.actor_user_id,
            "actor_name": actor_name,
            "source": data.source.value,
            "external_record_id": data.external_record_id,
            "remark": data.remark,
            "is_voided": False,
        }
        return project, values

    @staticmethod
    def _same_business_content(item, values, data) -> bool:
        compared_fields = set(values) - {"is_voided"}
        if data.actor_name is None:
            compared_fields.discard("actor_name")
        return all(getattr(item, name) == values[name] for name in compared_fields)

    @staticmethod
    def _find_existing(unit: UnitOfWork, data: BeamTransportHandoverCreate):
        by_code = get_beam_transport_handover_by_code(
            unit.session, data.handover_code
        )
        by_external = None
        if data.external_record_id is not None:
            by_external = get_beam_transport_handover_by_external_key(
                unit.session, data.source.value, data.external_record_id
            )
        if by_code is not None and by_external is not None and by_code.id != by_external.id:
            raise ResourceConflictError("交接编码和外部幂等标识指向不同记录")
        return by_code or by_external

    def record(self, data: BeamTransportHandoverCreate) -> BeamTransportHandoverRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的运输交接内容")
                if project is not None and not project.is_active:
                    raise InactiveResourceError("项目未启用")
                item = create_beam_transport_handover(unit.session, values)
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            return self._recover_concurrent_record(data)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def _recover_concurrent_record(
        self, data: BeamTransportHandoverCreate
    ) -> BeamTransportHandoverRead:
        try:
            with self._unit_of_work_factory() as unit:
                project, values = self._resolve_create_values(unit, data)
                existing = self._find_existing(unit, data)
                if existing is not None:
                    if self._same_business_content(existing, values, data):
                        return _to_read(existing)
                    raise ResourceConflictError("幂等标识已用于不同的运输交接内容")
                if project is not None and not project.is_active:
                    raise InactiveResourceError("项目未启用")
                raise ResourceAlreadyExistsError(
                    f"运输交接编码已存在: {data.handover_code}"
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        handover_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamTransportHandoverRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_transport_handover_by_code(
                    unit.session, handover_code
                )
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamTransportHandoverNotFoundError(
                        f"运输交接记录不存在: handover_code={handover_code}"
                    )
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamTransportHandoverFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamTransportHandoverSortField = BeamTransportHandoverSortField.OCCURRED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[BeamTransportHandoverSummary]:
        filters = filters or BeamTransportHandoverFilter()
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        project_code = values.pop("project_code", None)
        for field in ("handover_types", "result_codes", "sources"):
            if field in values:
                values[field] = [value.value for value in values[field]]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_transport_handovers(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[BeamTransportHandoverSummary](
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
        handover_code: str,
        data: BeamTransportHandoverVoid,
        *,
        project_code: str | None = None,
    ) -> BeamTransportHandoverRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_transport_handover_by_code(
                    unit.session, handover_code, for_update=True
                )
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamTransportHandoverNotFoundError(
                        f"运输交接记录不存在: handover_code={handover_code}"
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
                set_beam_transport_handover_voided(
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
