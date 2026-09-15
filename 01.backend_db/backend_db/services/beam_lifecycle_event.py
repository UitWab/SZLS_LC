import base64
import binascii
import json
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from backend_db.crud.beam_lifecycle_event import (
    get_beam_lifecycle_event,
    list_beam_lifecycle_events,
    list_beam_lifecycle_events_after,
)
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamLifecycleEventNotFoundError,
    InvalidDataError,
)
from backend_db.schemas import (
    BeamLifecycleEventFilter,
    BeamLifecycleEventRead,
    BeamLifecycleEventSortField,
    BeamLifecycleEventSummary,
    CursorPageRequest,
    CursorPageResult,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services._errors import raise_database_error
from backend_db.services._project_scope import resolve_project_scope


def _to_summary(item) -> BeamLifecycleEventSummary:
    return BeamLifecycleEventSummary(
        id=item.id,
        project_code=None if item.project is None else item.project.project_code,
        beam_code=item.beam.beam_code,
        event_type=item.event_type,
        status_before=item.status_before,
        status_after=item.status_after,
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
        work_order_code=(
            None if item.work_order is None else item.work_order.work_order_code
        ),
        occurred_at=item.occurred_at,
    )


def _to_read(item) -> BeamLifecycleEventRead:
    return BeamLifecycleEventRead(
        **_to_summary(item).model_dump(),
        beam_id=item.beam_id,
        source_position_id=item.source_position_id,
        target_position_id=item.target_position_id,
        work_order_id=item.work_order_id,
        created_at=item.created_at,
    )


def _encode_cursor(event_id: int) -> str:
    payload = json.dumps(
        [2, event_id],
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.b64decode(
                cursor + padding,
                altchars=b"-_",
                validate=True,
            ).decode("utf-8")
        )
        if not isinstance(payload, list) or len(payload) != 2 or payload[0] != 2:
            raise ValueError
        event_id = payload[1]
        if type(event_id) is not int or event_id <= 0:
            raise ValueError
        return event_id
    except (TypeError, ValueError, UnicodeError, binascii.Error) as error:
        raise InvalidDataError("梁生命周期事件游标无效") from error


def _filter_values(filters: BeamLifecycleEventFilter):
    values = filters.model_dump(exclude_none=True, mode="python")
    project_code = values.pop("project_code", None)
    if "event_types" in values:
        values["event_types"] = [item.value for item in filters.event_types or []]
    return project_code, values


class BeamLifecycleEventService:
    """只读梁生命周期历史；事件由 A 的梁操作在事务内自动追加。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def get(
        self,
        event_id: int,
        *,
        project_code: str | None = None,
    ) -> BeamLifecycleEventRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                item = get_beam_lifecycle_event(
                    unit.session,
                    event_id,
                    project_id=None if project is None else project.id,
                )
                if item is None:
                    raise BeamLifecycleEventNotFoundError(
                        f"梁生命周期事件不存在: id={event_id}"
                    )
                return _to_read(item)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: BeamLifecycleEventFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamLifecycleEventSortField = BeamLifecycleEventSortField.OCCURRED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> PageResult[BeamLifecycleEventSummary]:
        filters = filters or BeamLifecycleEventFilter()
        page_request = page_request or PageRequest()
        project_code, values = _filter_values(filters)
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, total, has_next = list_beam_lifecycle_events(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[BeamLifecycleEventSummary](
                    items=[_to_summary(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list_after(
        self,
        filters: BeamLifecycleEventFilter | None = None,
        cursor_request: CursorPageRequest | None = None,
    ) -> CursorPageResult[BeamLifecycleEventSummary]:
        filters = filters or BeamLifecycleEventFilter()
        cursor_request = cursor_request or CursorPageRequest()
        project_code, values = _filter_values(filters)
        after_id = _decode_cursor(cursor_request.cursor)
        try:
            with self._unit_of_work_factory() as unit:
                project = resolve_project_scope(unit, project_code)
                items, has_more = list_beam_lifecycle_events_after(
                    unit.session,
                    **values,
                    project_id=None if project is None else project.id,
                    after_id=after_id,
                    limit=cursor_request.limit,
                )
                next_cursor = cursor_request.cursor
                if items:
                    last = items[-1]
                    next_cursor = _encode_cursor(last.id)
                return CursorPageResult[BeamLifecycleEventSummary](
                    items=[_to_summary(item) for item in items],
                    next_cursor=next_cursor,
                    has_more=has_more,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)
