from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.beam_position_work_order import (
    create_beam_position_work_order,
    get_active_work_order_for_beam,
    get_beam_position_work_order,
    get_beam_position_work_order_by_code,
    list_beam_position_work_orders,
    set_beam_position_work_order_state,
)
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamPositionWorkOrderNotFoundError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
)
from backend_db.schemas import (
    BeamPositionWorkOrderCreate,
    BeamPositionWorkOrderFilter,
    BeamPositionWorkOrderRead,
    BeamPositionWorkOrderSortField,
    BeamPositionWorkOrderStatus,
    BeamPositionWorkOrderSummary,
    BeamPositionWorkOrderType,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._beam_positioning import (
    get_active_position,
    get_locked_beam,
    place_beam,
    release_beam,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import matches_project_scope, resolve_project_scope


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_summary(item) -> BeamPositionWorkOrderSummary:
    return BeamPositionWorkOrderSummary(
        id=item.id,
        project_code=None if item.project is None else item.project.project_code,
        work_order_code=item.work_order_code,
        order_type=item.order_type,
        beam_code=item.beam.beam_code,
        source_position_code=(
            None
            if item.source_position is None
            else item.source_position.position_code
        ),
        target_position_code=(
            None
            if item.target_position is None
            else item.target_position.position_code
        ),
        status=item.status,
        planned_at=item.planned_at,
        started_at=item.started_at,
        finished_at=item.finished_at,
    )


def _to_read(item) -> BeamPositionWorkOrderRead:
    return BeamPositionWorkOrderRead(
        **_to_summary(item).model_dump(),
        beam_id=item.beam_id,
        source_position_id=item.source_position_id,
        target_position_id=item.target_position_id,
        remark=item.remark,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class BeamPositionWorkOrderService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: BeamPositionWorkOrderCreate) -> BeamPositionWorkOrderRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, data.project_code, require_active=True)
                beam = get_locked_beam(unit, data.beam_code, project=project)
                if get_active_work_order_for_beam(unit.session, beam.id):
                    raise ResourceConflictError("该梁已有未结束的梁位工单")
                source = beam.current_position
                target = None
                if data.target_position_code:
                    target = get_active_position(
                        unit, data.target_position_code, project_id=beam.project_id
                    )
                if data.order_type == BeamPositionWorkOrderType.PLACE and source:
                    raise ResourceConflictError("PLACE 工单要求梁当前没有梁位")
                if (
                    data.order_type
                    in {
                        BeamPositionWorkOrderType.MOVE,
                        BeamPositionWorkOrderType.RELEASE,
                    }
                    and source is None
                ):
                    raise ResourceConflictError("MOVE 和 RELEASE 工单要求梁已有梁位")
                if data.order_type == BeamPositionWorkOrderType.MOVE:
                    if target is None:
                        raise ResourceConflictError("MOVE 工单缺少目标梁位")
                    if target.id == source.id:
                        raise ResourceConflictError(
                            "MOVE 工单的目标梁位不能等于原梁位"
                        )
                item = create_beam_position_work_order(
                    unit.session,
                    project_id=beam.project_id,
                    work_order_code=data.work_order_code,
                    order_type=data.order_type.value,
                    beam_id=beam.id,
                    source_position_id=None if source is None else source.id,
                    target_position_id=None if target is None else target.id,
                    status=BeamPositionWorkOrderStatus.PENDING.value,
                    planned_at=data.planned_at,
                    remark=data.remark,
                )
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"梁位工单编码已存在: {data.work_order_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(
        self,
        work_order_id: int,
        *,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        return self._get_one(work_order_id=work_order_id, project_code=project_code)

    def get_by_code(
        self,
        work_order_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        return self._get_one(work_order_code=work_order_code, project_code=project_code)

    def _get_one(
        self,
        *,
        work_order_id: int | None = None,
        work_order_code: str | None = None,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = (
                    get_beam_position_work_order(unit.session, work_order_id)
                    if work_order_id is not None
                    else get_beam_position_work_order_by_code(
                        unit.session, work_order_code
                    )
                )
                project = resolve_project_scope(unit, project_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamPositionWorkOrderNotFoundError("梁位工单不存在")
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamPositionWorkOrderFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamPositionWorkOrderSortField = BeamPositionWorkOrderSortField.ID,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[BeamPositionWorkOrderSummary]:
        filters = filters or BeamPositionWorkOrderFilter()
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        project_code = values.pop("project_code", None)
        include_global = values.pop("include_global", False)
        for field in ("order_types", "statuses"):
            if field in values:
                values[field] = [value.value for value in values[field]]
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_position_work_orders(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    include_global=include_global,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[BeamPositionWorkOrderSummary](
                    items=[_to_summary(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def start(
        self,
        work_order_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        return self._transition(work_order_code, project_code, action="start")

    def complete(
        self,
        work_order_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        return self._transition(work_order_code, project_code, action="complete")

    def cancel(
        self,
        work_order_code: str,
        *,
        project_code: str | None = None,
    ) -> BeamPositionWorkOrderRead:
        return self._transition(work_order_code, project_code, action="cancel")

    def _transition(
        self,
        code: str,
        project_code: str | None,
        *,
        action: Literal["start", "complete", "cancel"],
    ) -> BeamPositionWorkOrderRead:
        try:
            with self._unit_of_work_factory() as unit:
                item = get_beam_position_work_order_by_code(
                    unit.session, code, for_update=True
                )
                project = resolve_project_scope(unit, project_code)
                if item is None or not matches_project_scope(item.project_id, project):
                    raise BeamPositionWorkOrderNotFoundError("梁位工单不存在")
                now = _utc_now()
                if action == "start":
                    if item.status != BeamPositionWorkOrderStatus.PENDING.value:
                        raise ResourceConflictError("只有待执行工单可以开始")
                    changes = {
                        "status": BeamPositionWorkOrderStatus.IN_PROGRESS.value,
                        "started_at": now,
                    }
                elif action == "cancel":
                    if item.status not in {
                        BeamPositionWorkOrderStatus.PENDING.value,
                        BeamPositionWorkOrderStatus.IN_PROGRESS.value,
                    }:
                        raise ResourceConflictError("只有未结束工单可以取消")
                    changes = {
                        "status": BeamPositionWorkOrderStatus.CANCELED.value,
                        "finished_at": now,
                    }
                elif action == "complete":
                    if item.status != BeamPositionWorkOrderStatus.IN_PROGRESS.value:
                        raise ResourceConflictError("只有执行中的工单可以完成")
                    if item.order_type not in {
                        BeamPositionWorkOrderType.PLACE.value,
                        BeamPositionWorkOrderType.MOVE.value,
                        BeamPositionWorkOrderType.RELEASE.value,
                    }:
                        raise ResourceConflictError("梁位工单类型无效")
                    beam = get_locked_beam(unit, item.beam.beam_code, project=project)
                    if beam.current_position_id != item.source_position_id:
                        raise ResourceConflictError("梁的当前位置已与工单原梁位不一致")
                    if item.order_type == BeamPositionWorkOrderType.RELEASE.value:
                        release_beam(unit, beam)
                    else:
                        if item.target_position is None:
                            raise ResourceConflictError("梁位工单缺少目标梁位")
                        place_beam(
                            unit, beam, item.target_position.position_code,
                            require_unpositioned=(
                                item.order_type
                                == BeamPositionWorkOrderType.PLACE.value
                            ),
                        )
                    changes = {
                        "status": BeamPositionWorkOrderStatus.COMPLETED.value,
                        "finished_at": now,
                    }
                else:
                    raise ValueError(f"不支持的梁位工单动作: {action}")
                set_beam_position_work_order_state(unit.session, item, changes)
                result = _to_read(item)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceConflictError("目标梁位已被占用") from None
        except SQLAlchemyError as error:
            raise_database_error(error)
