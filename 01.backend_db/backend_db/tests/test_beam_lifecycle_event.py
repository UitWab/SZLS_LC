import base64
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

import backend_db.services._beam_lifecycle as lifecycle_module
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BackendDBError,
    BeamNotFoundError,
    BeamLifecycleEventNotFoundError,
    InvalidDataError,
    PositionOccupiedError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    Beam,
    BeamLifecycleEvent,
    BeamPosition,
    BeamPositionWorkOrder,
    BeamType,
    Project,
    YardArea,
)
from backend_db.models.beam_lifecycle_event import BeamLifecycleEventStreamLock
from backend_db.schemas import (
    BeamCreate,
    BeamLifecycleEventFilter,
    BeamLifecycleEventType,
    BeamPositionCommand,
    BeamPositionCreate,
    BeamPositionWorkOrderCreate,
    BeamPositionWorkOrderType,
    BeamStatus,
    BeamStatusChange,
    BeamTypeCreate,
    CursorPageRequest,
    PageRequest,
    ProjectCreate,
    SortOrder,
    YardAreaCreate,
)
from backend_db.services import BeamService


def _setup(suffix: str, *, beam_count: int = 1):
    services = create_database_services()
    project_code = f"EVENT_PROJECT_{suffix}"
    area_code = f"EVENT_AREA_{suffix}"
    type_code = f"EVENT_TYPE_{suffix}"
    position_codes = [f"EVENT_POS_{suffix}_{number}" for number in range(2)]
    beam_codes = [f"EVENT_BEAM_{suffix}_{number}" for number in range(beam_count)]

    services.projects.create(
        ProjectCreate(project_code=project_code, project_name=project_code)
    )
    services.yard_areas.create(
        YardAreaCreate(
            project_code=project_code,
            area_code=area_code,
            area_name=area_code,
            area_type="STORAGE",
        )
    )
    for position_code in position_codes:
        services.beam_positions.create(
            BeamPositionCreate(
                project_code=project_code,
                area_code=area_code,
                position_code=position_code,
            )
        )
    services.beam_types.create(
        BeamTypeCreate(
            project_code=project_code,
            type_code=type_code,
            type_name=type_code,
        )
    )
    for beam_code in beam_codes:
        services.beams.create(
            BeamCreate(
                project_code=project_code,
                beam_code=beam_code,
                beam_type_code=type_code,
            )
        )
    return services, project_code, beam_codes, position_codes


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        project_ids = list(
            session.scalars(
                select(Project.id).where(Project.project_code.contains(suffix))
            )
        )
        beam_ids = select(Beam.id).where(Beam.beam_code.contains(suffix))
        session.execute(
            delete(BeamLifecycleEvent).where(
                BeamLifecycleEvent.beam_id.in_(beam_ids)
            )
        )
        session.execute(
            delete(BeamPositionWorkOrder).where(
                BeamPositionWorkOrder.work_order_code.contains(suffix)
            )
        )
        session.execute(delete(Beam).where(Beam.beam_code.contains(suffix)))
        session.execute(
            delete(BeamPosition).where(BeamPosition.position_code.contains(suffix))
        )
        session.execute(delete(BeamType).where(BeamType.type_code.contains(suffix)))
        session.execute(delete(YardArea).where(YardArea.area_code.contains(suffix)))
        session.execute(delete(Project).where(Project.project_code.contains(suffix)))
        scope_keys = [f"PROJECT:{project_id}" for project_id in project_ids]
        scope_keys.append("GLOBAL")
        session.execute(
            delete(BeamLifecycleEventStreamLock).where(
                BeamLifecycleEventStreamLock.scope_key.in_(scope_keys)
            )
        )


def _events(services, project_code: str, beam_code: str):
    return services.beam_events.list(
        BeamLifecycleEventFilter(
            project_code=project_code,
            beam_code=beam_code,
        ),
        PageRequest(page_size=100),
        sort_order=SortOrder.ASC,
    ).items


def test_direct_beam_operations_append_only_real_lifecycle_changes():
    suffix = uuid4().hex[:8]
    services, project, beams, positions = _setup(suffix)
    beam = beams[0]
    try:
        services.beams.change_status(
            beam,
            BeamStatusChange(status=BeamStatus.REBAR_BINDING),
            project_code=project,
        )
        services.beams.change_status(
            beam,
            BeamStatusChange(status=BeamStatus.REBAR_BINDING),
            project_code=project,
        )
        services.beams.assign_position(
            beam,
            BeamPositionCommand(position_code=positions[0]),
            project_code=project,
        )
        services.beams.move_beam(
            beam,
            BeamPositionCommand(position_code=positions[0]),
            project_code=project,
        )
        services.beams.move_beam(
            beam,
            BeamPositionCommand(position_code=positions[1]),
            project_code=project,
        )
        services.beams.release_position(beam, project_code=project)
        services.beams.release_position(beam, project_code=project)

        events = _events(services, project, beam)
        assert [event.event_type for event in events] == [
            BeamLifecycleEventType.BEAM_CREATED,
            BeamLifecycleEventType.STATUS_CHANGED,
            BeamLifecycleEventType.POSITION_ASSIGNED,
            BeamLifecycleEventType.POSITION_MOVED,
            BeamLifecycleEventType.POSITION_RELEASED,
        ]
        assert events[0].status_before is None
        assert events[0].status_after == BeamStatus.UNPRODUCED
        assert events[1].status_before == BeamStatus.UNPRODUCED
        assert events[1].status_after == BeamStatus.REBAR_BINDING
        assert events[2].source_position_code is None
        assert events[2].target_position_code == positions[0]
        assert events[3].source_position_code == positions[0]
        assert events[3].target_position_code == positions[1]
        assert events[4].source_position_code == positions[1]
        assert events[4].target_position_code is None
        assert all(event.work_order_code is None for event in events)

        first_page = services.beam_events.list(
            BeamLifecycleEventFilter(project_code=project, beam_code=beam),
            PageRequest(page_size=2),
            sort_order=SortOrder.ASC,
        )
        assert first_page.total == 5
        assert first_page.has_next is True
        assert [event.id for event in first_page.items] == [
            events[0].id,
            events[1].id,
        ]
        status_events = services.beam_events.list(
            BeamLifecycleEventFilter(
                project_code=project,
                beam_code=beam,
                event_types=[BeamLifecycleEventType.STATUS_CHANGED],
                occurred_at_from=events[1].occurred_at,
                occurred_at_to=events[1].occurred_at,
            )
        )
        assert [event.id for event in status_events.items] == [events[1].id]
    finally:
        _cleanup(suffix)


def test_work_order_only_records_one_linked_event_when_completed():
    suffix = uuid4().hex[:8]
    services, project, beams, positions = _setup(suffix)
    beam = beams[0]
    canceled_code = f"EVENT_CANCEL_{suffix}"
    completed_code = f"EVENT_COMPLETE_{suffix}"
    try:
        baseline = len(_events(services, project, beam))
        services.position_work_orders.create(
            BeamPositionWorkOrderCreate(
                project_code=project,
                work_order_code=canceled_code,
                beam_code=beam,
                order_type=BeamPositionWorkOrderType.PLACE,
                target_position_code=positions[0],
            )
        )
        services.position_work_orders.start(canceled_code, project_code=project)
        services.position_work_orders.cancel(canceled_code, project_code=project)
        assert len(_events(services, project, beam)) == baseline

        work_order = services.position_work_orders.create(
            BeamPositionWorkOrderCreate(
                project_code=project,
                work_order_code=completed_code,
                beam_code=beam,
                order_type=BeamPositionWorkOrderType.PLACE,
                target_position_code=positions[0],
            )
        )
        services.position_work_orders.start(completed_code, project_code=project)
        assert len(_events(services, project, beam)) == baseline
        services.position_work_orders.complete(completed_code, project_code=project)

        events = _events(services, project, beam)
        assert len(events) == baseline + 1
        event = events[-1]
        assert event.event_type == BeamLifecycleEventType.POSITION_ASSIGNED
        assert event.work_order_code == completed_code
        assert services.beam_events.get(
            event.id, project_code=project
        ).work_order_id == work_order.id
    finally:
        _cleanup(suffix)


def test_failed_position_change_rolls_back_without_event():
    suffix = uuid4().hex[:8]
    services, project, beams, positions = _setup(suffix, beam_count=2)
    try:
        services.beams.assign_position(
            beams[0],
            BeamPositionCommand(position_code=positions[0]),
            project_code=project,
        )
        services.beams.assign_position(
            beams[1],
            BeamPositionCommand(position_code=positions[1]),
            project_code=project,
        )
        before_ids = [event.id for event in _events(services, project, beams[0])]

        with pytest.raises(PositionOccupiedError):
            services.beams.move_beam(
                beams[0],
                BeamPositionCommand(position_code=positions[1]),
                project_code=project,
            )

        after = _events(services, project, beams[0])
        assert [event.id for event in after] == before_ids
        assert services.beams.get_by_code(
            beams[0], project_code=project
        ).current_position_code == positions[0]
    finally:
        _cleanup(suffix)


def test_cursor_is_stable_for_equal_timestamps_and_rejects_invalid_input(monkeypatch):
    suffix = uuid4().hex[:8]
    fixed_time = datetime(2026, 9, 14, 12, 0, 0)
    monkeypatch.setattr(lifecycle_module, "_utc_now", lambda: fixed_time)
    services, project, beams, _ = _setup(suffix)
    beam = beams[0]
    try:
        for status in (
            BeamStatus.REBAR_BINDING,
            BeamStatus.REBAR_CHECK,
            BeamStatus.FORMWORK_CHECK,
            BeamStatus.CONCRETE_CASTING,
        ):
            services.beams.change_status(
                beam,
                BeamStatusChange(status=status),
                project_code=project,
            )

        filters = BeamLifecycleEventFilter(project_code=project, beam_code=beam)
        first = services.beam_events.list_after(
            filters, CursorPageRequest(limit=2)
        )
        second = services.beam_events.list_after(
            filters, CursorPageRequest(cursor=first.next_cursor, limit=2)
        )
        third = services.beam_events.list_after(
            filters, CursorPageRequest(cursor=second.next_cursor, limit=2)
        )
        empty = services.beam_events.list_after(
            filters, CursorPageRequest(cursor=third.next_cursor, limit=2)
        )

        event_ids = [
            event.id
            for page in (first, second, third)
            for event in page.items
        ]
        assert len(event_ids) == 5
        assert event_ids == sorted(set(event_ids))
        assert first.has_more is True
        assert second.has_more is True
        assert third.has_more is False
        assert empty.items == []
        assert empty.next_cursor == third.next_cursor
        assert empty.has_more is False

        with pytest.raises(InvalidDataError):
            services.beam_events.list_after(
                filters, CursorPageRequest(cursor="not-a-valid-cursor")
            )
        old_cursor = base64.urlsafe_b64encode(
            json.dumps([1, fixed_time.isoformat(timespec="microseconds"), 1])
            .encode("utf-8")
        ).decode("ascii").rstrip("=")
        with pytest.raises(InvalidDataError):
            services.beam_events.list_after(
                filters, CursorPageRequest(cursor=old_cursor)
            )
        for invalid_event_id in (1.5, True, "1", None, 0, -1, float("nan")):
            invalid_cursor = base64.urlsafe_b64encode(
                json.dumps([2, invalid_event_id]).encode("utf-8")
            ).decode("ascii").rstrip("=")
            with pytest.raises(InvalidDataError):
                services.beam_events.list_after(
                    filters, CursorPageRequest(cursor=invalid_cursor)
                )
    finally:
        _cleanup(suffix)


def test_same_project_event_writes_cannot_commit_past_incremental_cursor(monkeypatch):
    suffix = uuid4().hex[:8]
    services, project, _, _ = _setup(suffix, beam_count=0)
    beams = [f"EVENT_CONCURRENT_{suffix}_{number}" for number in range(2)]
    type_code = f"EVENT_TYPE_{suffix}"
    filters = BeamLifecycleEventFilter(project_code=project)
    baseline = services.beam_events.list_after(
        filters, CursorPageRequest(limit=100)
    )
    original_create = lifecycle_module.create_beam_lifecycle_event
    first_inserted = Event()
    release_first = Event()
    second_entered = Event()

    def controlled_create(session, **values):
        if not first_inserted.is_set():
            item = original_create(session, **values)
            first_inserted.set()
            assert release_first.wait(timeout=5)
            return item
        second_entered.set()
        return original_create(session, **values)

    monkeypatch.setattr(
        lifecycle_module,
        "create_beam_lifecycle_event",
        controlled_create,
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                services.beams.create,
                BeamCreate(
                    project_code=project,
                    beam_code=beams[0],
                    beam_type_code=type_code,
                ),
            )
            assert first_inserted.wait(timeout=5)
            second = executor.submit(
                services.beams.create,
                BeamCreate(
                    project_code=project,
                    beam_code=beams[1],
                    beam_type_code=type_code,
                ),
            )
            assert second_entered.wait(timeout=5)
            with pytest.raises(FutureTimeoutError):
                second.result(timeout=0.2)

            while_first_is_open = services.beam_events.list_after(
                filters,
                CursorPageRequest(cursor=baseline.next_cursor, limit=100),
            )
            assert while_first_is_open.items == []

            release_first.set()
            first.result(timeout=5)
            second.result(timeout=5)

        committed = services.beam_events.list_after(
            filters,
            CursorPageRequest(cursor=baseline.next_cursor, limit=100),
        )
        assert [event.beam_code for event in committed.items] == beams
        assert [event.event_type for event in committed.items] == [
            BeamLifecycleEventType.BEAM_CREATED,
            BeamLifecycleEventType.BEAM_CREATED,
        ]
        assert [event.id for event in committed.items] == sorted(
            event.id for event in committed.items
        )
    finally:
        release_first.set()
        _cleanup(suffix)


def test_different_project_event_writes_do_not_block_each_other(monkeypatch):
    first_suffix = uuid4().hex[:8]
    second_suffix = uuid4().hex[:8]
    services, first_project, _, _ = _setup(first_suffix, beam_count=0)
    _, second_project, _, _ = _setup(second_suffix, beam_count=0)
    first_beam = f"EVENT_CONCURRENT_{first_suffix}"
    second_beam = f"EVENT_CONCURRENT_{second_suffix}"
    first_project_id = services.projects.get_by_code(first_project).id
    original_create = lifecycle_module.create_beam_lifecycle_event
    first_inserted = Event()
    release_first = Event()

    def controlled_create(session, **values):
        item = original_create(session, **values)
        if values["project_id"] == first_project_id:
            first_inserted.set()
            assert release_first.wait(timeout=5)
        return item

    monkeypatch.setattr(
        lifecycle_module,
        "create_beam_lifecycle_event",
        controlled_create,
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                services.beams.create,
                BeamCreate(
                    project_code=first_project,
                    beam_code=first_beam,
                    beam_type_code=f"EVENT_TYPE_{first_suffix}",
                ),
            )
            assert first_inserted.wait(timeout=5)
            second = executor.submit(
                services.beams.create,
                BeamCreate(
                    project_code=second_project,
                    beam_code=second_beam,
                    beam_type_code=f"EVENT_TYPE_{second_suffix}",
                ),
            )
            second.result(timeout=5)
            release_first.set()
            first.result(timeout=5)

        assert len(_events(services, first_project, first_beam)) == 1
        assert len(_events(services, second_project, second_beam)) == 1
    finally:
        release_first.set()
        _cleanup(first_suffix)
        _cleanup(second_suffix)


def test_event_lookup_respects_project_scope():
    first_suffix = uuid4().hex[:8]
    second_suffix = uuid4().hex[:8]
    services, first_project, first_beams, _ = _setup(first_suffix)
    _, second_project, _, _ = _setup(second_suffix)
    try:
        event = _events(services, first_project, first_beams[0])[0]
        with pytest.raises(BeamLifecycleEventNotFoundError):
            services.beam_events.get(event.id, project_code=second_project)
    finally:
        _cleanup(first_suffix)
        _cleanup(second_suffix)


def test_global_beam_event_remains_in_global_scope():
    suffix = uuid4().hex[:8]
    services = create_database_services()
    type_code = f"EVENT_GLOBAL_TYPE_{suffix}"
    beam_code = f"EVENT_GLOBAL_BEAM_{suffix}"
    try:
        services.beam_types.create(
            BeamTypeCreate(type_code=type_code, type_name=type_code)
        )
        services.beams.create(
            BeamCreate(beam_code=beam_code, beam_type_code=type_code)
        )
        events = services.beam_events.list(
            BeamLifecycleEventFilter(beam_code=beam_code)
        ).items
        assert len(events) == 1
        assert events[0].project_code is None
        assert events[0].event_type == BeamLifecycleEventType.BEAM_CREATED
    finally:
        _cleanup(suffix)


def test_commit_failure_rolls_back_beam_and_creation_event():
    class FailingCommitUnitOfWork(UnitOfWork):
        def commit(self) -> None:
            raise SQLAlchemyError("forced commit failure")

    suffix = uuid4().hex[:8]
    services, project, _, _ = _setup(suffix, beam_count=0)
    beam_code = f"EVENT_FAILED_BEAM_{suffix}"
    type_code = f"EVENT_TYPE_{suffix}"
    failing_beams = BeamService(unit_of_work_factory=FailingCommitUnitOfWork)
    try:
        with pytest.raises(BackendDBError):
            failing_beams.create(
                BeamCreate(
                    project_code=project,
                    beam_code=beam_code,
                    beam_type_code=type_code,
                )
            )
        with pytest.raises(BeamNotFoundError):
            services.beams.get_by_code(beam_code, project_code=project)
        assert services.beam_events.list(
            BeamLifecycleEventFilter(project_code=project, beam_code=beam_code)
        ).items == []
        services.beams.create(
            BeamCreate(
                project_code=project,
                beam_code=beam_code,
                beam_type_code=type_code,
            )
        )
        assert len(services.beam_events.list(
            BeamLifecycleEventFilter(project_code=project, beam_code=beam_code)
        ).items) == 1
    finally:
        _cleanup(suffix)
