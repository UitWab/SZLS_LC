from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select

import backend_db.services.beam_position_work_order as work_order_service_module

from backend_db.crud.beam_position_work_order import (
    create_beam_position_work_order,
    set_beam_position_work_order_state,
)
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    BeamPositionWorkOrderNotFoundError,
    InactiveResourceError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    Beam,
    BeamLifecycleEvent,
    BeamPosition,
    BeamPositionWorkOrder,
)
from backend_db.models import BeamType, Project, YardArea
from backend_db.schemas import (
    BeamCreate,
    BeamPositionCommand,
    BeamPositionCreate,
    BeamPositionWorkOrderCreate,
    BeamPositionWorkOrderFilter,
    BeamPositionWorkOrderSortField,
    BeamPositionWorkOrderStatus,
    BeamPositionWorkOrderType,
    BeamTypeCreate,
    PageRequest,
    ProjectCreate,
    SortOrder,
    YardAreaCreate,
)


def _setup(suffix):
    services = create_database_services()
    project_code = f"WO_PROJECT_{suffix}"
    area_code = f"WO_AREA_{suffix}"
    type_code = f"WO_TYPE_{suffix}"
    beam_code = f"WO_BEAM_{suffix}"
    positions = [f"WO_POS_{suffix}_{n}" for n in range(2)]
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
    for code in positions:
        services.beam_positions.create(
            BeamPositionCreate(
                project_code=project_code,
                area_code=area_code,
                position_code=code,
            )
        )
    services.beam_types.create(
        BeamTypeCreate(
            project_code=project_code,
            type_code=type_code,
            type_name=type_code,
        )
    )
    services.beams.create(
        BeamCreate(
            project_code=project_code,
            beam_code=beam_code,
            beam_type_code=type_code,
        )
    )
    return services, project_code, beam_code, positions


def _cleanup(suffix):
    with SessionLocal.begin() as session:
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
        session.execute(delete(BeamPosition).where(BeamPosition.position_code.contains(suffix)))
        session.execute(delete(BeamType).where(BeamType.type_code.contains(suffix)))
        session.execute(delete(YardArea).where(YardArea.area_code.contains(suffix)))
        session.execute(delete(Project).where(Project.project_code.contains(suffix)))


def _create(services, project_code, beam_code, code, order_type, target=None):
    return services.position_work_orders.create(
        BeamPositionWorkOrderCreate(
            project_code=project_code,
            work_order_code=code,
            beam_code=beam_code,
            order_type=order_type,
            target_position_code=target,
        )
    )


def test_position_work_order_place_move_release_lifecycle():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    try:
        place = _create(
            services,
            project,
            beam,
            f"PLACE_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )
        assert place.status == BeamPositionWorkOrderStatus.PENDING
        assert place.source_position_code is None
        assert services.beams.get_by_code(beam, project_code=project).current_position_code is None
        with pytest.raises(ResourceConflictError):
            _create(
                services,
                project,
                beam,
                f"DUP_{suffix}",
                BeamPositionWorkOrderType.PLACE,
                positions[0],
            )
        services.position_work_orders.start(place.work_order_code, project_code=project)
        completed = services.position_work_orders.complete(
            place.work_order_code, project_code=project
        )
        assert completed.status == BeamPositionWorkOrderStatus.COMPLETED
        assert services.beams.get_by_code(beam, project_code=project).current_position_code == positions[0]

        move = _create(
            services,
            project,
            beam,
            f"MOVE_{suffix}",
            BeamPositionWorkOrderType.MOVE,
            positions[1],
        )
        assert move.source_position_code == positions[0]
        services.position_work_orders.start(move.work_order_code, project_code=project)
        services.position_work_orders.complete(move.work_order_code, project_code=project)
        assert services.beams.get_by_code(beam, project_code=project).current_position_code == positions[1]

        release = _create(
            services,
            project,
            beam,
            f"RELEASE_{suffix}",
            BeamPositionWorkOrderType.RELEASE,
        )
        services.position_work_orders.start(release.work_order_code, project_code=project)
        services.position_work_orders.complete(release.work_order_code, project_code=project)
        assert services.beams.get_by_code(beam, project_code=project).current_position_code is None
    finally:
        _cleanup(suffix)


def test_position_work_order_cancel_and_listing():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    try:
        item = _create(
            services,
            project,
            beam,
            f"CANCEL_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )
        canceled = services.position_work_orders.cancel(item.work_order_code, project_code=project)
        assert canceled.status == BeamPositionWorkOrderStatus.CANCELED
        replacement = _create(
            services,
            project,
            beam,
            f"NEXT_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[1],
        )
        page = services.position_work_orders.list(
            BeamPositionWorkOrderFilter(project_code=project, beam_code=beam)
        )
        assert {row.id for row in page.items} == {item.id, replacement.id}
        assert services.position_work_orders.get_by_code(
            replacement.work_order_code, project_code=project
        ).id == replacement.id
        with pytest.raises(ResourceConflictError):
            services.position_work_orders.complete(
                replacement.work_order_code, project_code=project
            )
    finally:
        _cleanup(suffix)


def test_position_work_order_create_schema_enforces_type_shape():
    common = {"work_order_code": "WO", "beam_code": "BEAM"}
    with pytest.raises(ValidationError):
        BeamPositionWorkOrderCreate(**common, order_type="PLACE")
    with pytest.raises(ValidationError):
        BeamPositionWorkOrderCreate(
            **common, order_type="RELEASE", target_position_code="P1"
        )


def test_position_work_order_completion_rolls_back_when_target_is_occupied():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    second_beam = f"WO_BEAM_SECOND_{suffix}"
    try:
        services.beams.assign_position(
            beam, BeamPositionCommand(position_code=positions[0]),
            project_code=project,
        )
        item = _create(
            services,
            project,
            beam,
            f"OCCUPIED_{suffix}",
            BeamPositionWorkOrderType.MOVE,
            positions[1],
        )
        services.position_work_orders.start(item.work_order_code, project_code=project)
        services.beams.create(BeamCreate(
            project_code=project, beam_code=second_beam,
            beam_type_code=f"WO_TYPE_{suffix}",
        ))
        services.beams.assign_position(
            second_beam, BeamPositionCommand(position_code=positions[1]),
            project_code=project,
        )

        with pytest.raises(ResourceConflictError):
            services.position_work_orders.complete(item.work_order_code, project_code=project)
        assert services.beams.get_by_code(
            beam, project_code=project
        ).current_position_code == positions[0]
        assert services.position_work_orders.get_by_code(
            item.work_order_code, project_code=project
        ).status == BeamPositionWorkOrderStatus.IN_PROGRESS
    finally:
        _cleanup(suffix)


def test_position_work_order_isolated_by_project():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    other_project = f"WO_OTHER_PROJECT_{suffix}"
    try:
        services.projects.create(
            ProjectCreate(
                project_code=other_project,
                project_name=other_project,
            )
        )
        item = _create(
            services,
            project,
            beam,
            f"ISOLATED_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )

        with pytest.raises(BeamPositionWorkOrderNotFoundError):
            services.position_work_orders.get_by_code(
                item.work_order_code,
                project_code=other_project,
            )
        page = services.position_work_orders.list(
            BeamPositionWorkOrderFilter(project_code=other_project)
        )
        assert page.items == []
    finally:
        _cleanup(suffix)


def test_position_work_order_crud_rejects_business_field_updates():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    try:
        item = _create(
            services,
            project,
            beam,
            f"IMMUTABLE_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )
        with SessionLocal() as session:
            model = session.get(BeamPositionWorkOrder, item.id)
            with pytest.raises(ValueError, match="不允许更新梁位工单字段"):
                set_beam_position_work_order_state(
                    session,
                    model,
                    {"target_position_id": None},
                )
    finally:
        _cleanup(suffix)


def test_position_work_order_concurrent_create_allows_only_one_active(monkeypatch):
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    snapshot_barrier = Barrier(2)
    original_resolve_project_scope = work_order_service_module.resolve_project_scope

    def resolve_after_snapshot(*args, **kwargs):
        project_row = original_resolve_project_scope(*args, **kwargs)
        snapshot_barrier.wait(timeout=5)
        return project_row

    def create_concurrently(sequence: int):
        try:
            return _create(
                create_database_services(),
                project,
                beam,
                f"CONCURRENT_{sequence}_{suffix}",
                BeamPositionWorkOrderType.PLACE,
                positions[sequence],
            )
        except ResourceConflictError as error:
            return error

    try:
        monkeypatch.setattr(
            work_order_service_module,
            "resolve_project_scope",
            resolve_after_snapshot,
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create_concurrently, range(2)))
        monkeypatch.setattr(
            work_order_service_module,
            "resolve_project_scope",
            original_resolve_project_scope,
        )

        assert sum(not isinstance(result, Exception) for result in results) == 1
        assert sum(isinstance(result, ResourceConflictError) for result in results) == 1
        page = services.position_work_orders.list(
            BeamPositionWorkOrderFilter(
                project_code=project,
                beam_code=beam,
                statuses=[
                    BeamPositionWorkOrderStatus.PENDING,
                    BeamPositionWorkOrderStatus.IN_PROGRESS,
                ],
            )
        )
        assert len(page.items) == 1
    finally:
        _cleanup(suffix)


def test_position_work_order_rejects_duplicate_code_and_inactive_position():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    second_beam = f"WO_BEAM_SECOND_{suffix}"
    try:
        first = _create(
            services,
            project,
            beam,
            f"DUPLICATE_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )
        services.beams.create(
            BeamCreate(
                project_code=project,
                beam_code=second_beam,
                beam_type_code=f"WO_TYPE_{suffix}",
            )
        )
        with pytest.raises(ResourceAlreadyExistsError):
            _create(
                services,
                project,
                second_beam,
                first.work_order_code,
                BeamPositionWorkOrderType.PLACE,
                positions[1],
            )

        services.position_work_orders.cancel(first.work_order_code, project_code=project)
        target = services.beam_positions.get_by_code(
            positions[1], project_code=project
        )
        services.beam_positions.set_active(
            target.id, is_active=False, project_code=project
        )
        with pytest.raises(InactiveResourceError):
            _create(
                services,
                project,
                beam,
                f"INACTIVE_{suffix}",
                BeamPositionWorkOrderType.PLACE,
                positions[1],
            )
    finally:
        _cleanup(suffix)


def test_position_work_order_terminal_states_reject_further_transitions():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    try:
        completed = _create(
            services,
            project,
            beam,
            f"COMPLETED_{suffix}",
            BeamPositionWorkOrderType.PLACE,
            positions[0],
        )
        services.position_work_orders.start(
            completed.work_order_code, project_code=project
        )
        services.position_work_orders.complete(
            completed.work_order_code, project_code=project
        )

        canceled = _create(
            services,
            project,
            beam,
            f"CANCELED_{suffix}",
            BeamPositionWorkOrderType.RELEASE,
        )
        services.position_work_orders.cancel(
            canceled.work_order_code, project_code=project
        )

        for code in (completed.work_order_code, canceled.work_order_code):
            for transition in (
                services.position_work_orders.start,
                services.position_work_orders.complete,
                services.position_work_orders.cancel,
            ):
                with pytest.raises(ResourceConflictError):
                    transition(code, project_code=project)
    finally:
        _cleanup(suffix)


def test_position_work_order_no_total_pagination_has_stable_tie_breaker():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    planned_at = datetime(2026, 9, 7, 8, 0)
    try:
        created_ids = []
        for sequence in range(3):
            item = services.position_work_orders.create(
                BeamPositionWorkOrderCreate(
                    project_code=project,
                    work_order_code=f"PAGE_{sequence}_{suffix}",
                    beam_code=beam,
                    order_type=BeamPositionWorkOrderType.PLACE,
                    target_position_code=positions[0],
                    planned_at=planned_at,
                )
            )
            created_ids.append(item.id)
            services.position_work_orders.cancel(
                item.work_order_code, project_code=project
            )

        first_page = services.position_work_orders.list(
            BeamPositionWorkOrderFilter(project_code=project),
            PageRequest(page=1, page_size=2, include_total=False),
            sort_by=BeamPositionWorkOrderSortField.PLANNED_AT,
            sort_order=SortOrder.ASC,
        )
        second_page = services.position_work_orders.list(
            BeamPositionWorkOrderFilter(project_code=project),
            PageRequest(page=2, page_size=2, include_total=False),
            sort_by=BeamPositionWorkOrderSortField.PLANNED_AT,
            sort_order=SortOrder.ASC,
        )

        assert [item.id for item in first_page.items] == created_ids[:2]
        assert [item.id for item in second_page.items] == created_ids[2:]
        assert first_page.total is None
        assert first_page.has_next is True
        assert first_page.has_previous is False
        assert second_page.total is None
        assert second_page.has_next is False
        assert second_page.has_previous is True
    finally:
        _cleanup(suffix)


def test_position_work_order_crud_create_does_not_commit():
    suffix = uuid4().hex[:8]
    _, project, beam, positions = _setup(suffix)
    code = f"NO_COMMIT_{suffix}"
    try:
        with UnitOfWork() as unit:
            project_id = unit.session.scalar(
                select(Project.id).where(Project.project_code == project)
            )
            beam_id = unit.session.scalar(
                select(Beam.id).where(Beam.beam_code == beam)
            )
            target_position_id = unit.session.scalar(
                select(BeamPosition.id).where(
                    BeamPosition.position_code == positions[0]
                )
            )
            item = create_beam_position_work_order(
                unit.session,
                project_id=project_id,
                work_order_code=code,
                order_type=BeamPositionWorkOrderType.PLACE.value,
                beam_id=beam_id,
                source_position_id=None,
                target_position_id=target_position_id,
                status=BeamPositionWorkOrderStatus.PENDING.value,
            )
            assert item.id is not None

        with SessionLocal() as session:
            count = session.scalar(
                select(func.count()).select_from(BeamPositionWorkOrder).where(
                    BeamPositionWorkOrder.work_order_code == code
                )
            )
        assert count == 0
    finally:
        _cleanup(suffix)


def test_position_work_order_rejects_completion_after_source_position_changes():
    suffix = uuid4().hex[:8]
    services, project, beam, positions = _setup(suffix)
    try:
        services.beams.assign_position(
            beam,
            BeamPositionCommand(position_code=positions[0]),
            project_code=project,
        )
        item = _create(
            services,
            project,
            beam,
            f"STALE_SOURCE_{suffix}",
            BeamPositionWorkOrderType.MOVE,
            positions[1],
        )
        services.position_work_orders.start(
            item.work_order_code,
            project_code=project,
        )
        services.beams.release_position(beam, project_code=project)

        with pytest.raises(ResourceConflictError, match="原梁位不一致"):
            services.position_work_orders.complete(
                item.work_order_code,
                project_code=project,
            )
        assert services.position_work_orders.get_by_code(
            item.work_order_code,
            project_code=project,
        ).status == BeamPositionWorkOrderStatus.IN_PROGRESS
    finally:
        _cleanup(suffix)
