from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import delete

import backend_db.services.beam_position as beam_position_service_module
from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import (
    BeamAlreadyPositionedError,
    BeamPositionNotFoundError,
    BeamTypeNotFoundError,
    InactiveResourceError,
    InvalidAreaHierarchyError,
    PositionOccupiedError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    YardAreaNotFoundError,
)
from backend_db.models import Beam, BeamPosition, BeamType, YardArea
from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamPositionCreate,
    BeamPositionCommand,
    BeamPositionFilter,
    BeamPositionUpdate,
    BeamStatus,
    BeamStatusChange,
    BeamTypeCreate,
    BeamUpdate,
    PageRequest,
    YardAreaCreate,
    YardAreaFilter,
    YardAreaUpdate,
)
from backend_db.services import (
    BeamPositionService,
    BeamService,
    BeamTypeService,
    YardAreaService,
)


@pytest.fixture
def domain_prefix():
    prefix = f"TEST_DOMAIN_{uuid4().hex[:8]}"
    yield prefix
    with SessionLocal.begin() as session:
        session.execute(delete(Beam).where(Beam.beam_code.like(f"{prefix}%")))
        session.execute(
            delete(BeamPosition).where(
                BeamPosition.position_code.like(f"{prefix}%")
            )
        )
        session.execute(
            delete(YardArea).where(YardArea.area_code.like(f"{prefix}%"))
        )
        session.execute(
            delete(BeamType).where(BeamType.type_code.like(f"{prefix}%"))
        )


def _create_area(prefix: str, suffix: str = "AREA", **overrides):
    values = {
        "area_code": f"{prefix}_{suffix}",
        "area_name": f"区域{suffix}",
        "area_type": "storage",
    }
    values.update(overrides)
    return YardAreaService().create(YardAreaCreate(**values))


def _create_type(prefix: str, suffix: str = "TYPE", **overrides):
    values = {
        "type_code": f"{prefix}_{suffix}",
        "type_name": f"梁型{suffix}",
    }
    values.update(overrides)
    return BeamTypeService().create(BeamTypeCreate(**values))


def _create_position(prefix: str, area_code: str, suffix: str, **overrides):
    values = {
        "position_code": f"{prefix}_{suffix}",
        "position_name": f"梁位{suffix}",
        "area_code": area_code,
    }
    values.update(overrides)
    return BeamPositionService().create(BeamPositionCreate(**values))


def _create_beam(prefix: str, type_code: str, suffix: str, **overrides):
    values = {
        "beam_code": f"{prefix}_{suffix}",
        "beam_name": f"梁{suffix}",
        "beam_type_code": type_code,
    }
    values.update(overrides)
    return BeamService().create(BeamCreate(**values))


def test_yard_area_service_builds_tree_and_filters(domain_prefix):
    root = _create_area(domain_prefix, "ROOT", sort_order=2)
    child = _create_area(
        domain_prefix,
        "CHILD",
        parent_area_code=root.area_code,
        sort_order=1,
    )

    tree = YardAreaService().tree()
    matching_root = next(item for item in tree if item.area_code == root.area_code)
    assert [item.area_code for item in matching_root.children] == [child.area_code]

    page = YardAreaService().list(
        YardAreaFilter(parent_area_code=root.area_code),
    )
    assert [item.area_code for item in page.items] == [child.area_code]
    assert page.items[0].parent_area_code == root.area_code


def test_yard_area_service_rejects_duplicate_missing_parent_and_cycle(domain_prefix):
    root = _create_area(domain_prefix, "ROOT")
    child = _create_area(
        domain_prefix,
        "CHILD",
        parent_area_code=root.area_code,
    )

    with pytest.raises(ResourceAlreadyExistsError):
        _create_area(domain_prefix, "ROOT")
    with pytest.raises(YardAreaNotFoundError):
        _create_area(
            domain_prefix,
            "ORPHAN",
            parent_area_code=f"{domain_prefix}_MISSING",
        )
    with pytest.raises(InvalidAreaHierarchyError):
        YardAreaService().update(
            root.id,
            YardAreaUpdate(parent_area_code=child.area_code),
        )


def test_yard_area_deactivation_does_not_cascade(domain_prefix):
    root = _create_area(domain_prefix, "ROOT")
    child = _create_area(
        domain_prefix,
        "CHILD",
        parent_area_code=root.area_code,
    )

    with pytest.raises(ResourceConflictError):
        YardAreaService().set_active(root.id, is_active=False)

    assert YardAreaService().get(child.id).is_active is True
    YardAreaService().set_active(child.id, is_active=False)
    assert YardAreaService().set_active(root.id, is_active=False).is_active is False


def test_position_service_resolves_area_and_filters_occupancy(domain_prefix):
    area = _create_area(domain_prefix)
    position = _create_position(domain_prefix, area.area_code, "POS_A", x_mm="10.500")

    assert position.area_code == area.area_code
    assert position.current_beam_code is None
    page = BeamPositionService().list(
        BeamPositionFilter(area_code=area.area_code, is_occupied=False)
    )
    assert [item.position_code for item in page.items] == [position.position_code]

    updated = BeamPositionService().update(
        position.id,
        BeamPositionUpdate(position_name="更新后梁位", remark=None),
    )
    assert updated.position_name == "更新后梁位"


def test_position_service_rejects_missing_or_inactive_area(domain_prefix):
    with pytest.raises(YardAreaNotFoundError):
        _create_position(
            domain_prefix,
            f"{domain_prefix}_MISSING",
            "POS_MISSING",
        )

    area = _create_area(domain_prefix)
    YardAreaService().set_active(area.id, is_active=False)
    with pytest.raises(InactiveResourceError):
        _create_position(domain_prefix, area.area_code, "POS_INACTIVE")


def test_area_with_active_position_cannot_be_deactivated(domain_prefix):
    area = _create_area(domain_prefix)
    _create_position(domain_prefix, area.area_code, "POS")

    with pytest.raises(ResourceConflictError):
        YardAreaService().set_active(area.id, is_active=False)


def test_beam_service_rejects_missing_or_inactive_beam_type(domain_prefix):
    with pytest.raises(BeamTypeNotFoundError):
        _create_beam(
            domain_prefix,
            f"{domain_prefix}_MISSING_TYPE",
            "BEAM_MISSING_TYPE",
        )

    beam_type = _create_type(domain_prefix)
    BeamTypeService().set_active(beam_type.id, is_active=False)
    with pytest.raises(InactiveResourceError):
        _create_beam(
            domain_prefix,
            beam_type.type_code,
            "BEAM_INACTIVE_TYPE",
        )


def test_beam_service_creates_updates_status_and_filters(domain_prefix):
    beam_type = _create_type(domain_prefix)
    beam = _create_beam(domain_prefix, beam_type.type_code, "BEAM_A")

    assert beam.status is BeamStatus.UNPRODUCED
    updated = BeamService().update(
        beam.id,
        BeamUpdate(beam_name="更新后的梁", remark="测试"),
    )
    assert updated.beam_name == "更新后的梁"
    changed = BeamService().change_status(
        beam.beam_code,
        BeamStatusChange(status=BeamStatus.STORED),
    )
    assert changed.status is BeamStatus.STORED

    page = BeamService().list(
        BeamFilter(
            beam_type_code=beam_type.type_code,
            statuses=[BeamStatus.STORED],
        ),
        PageRequest(page_size=1),
    )
    assert [item.beam_code for item in page.items] == [beam.beam_code]
    assert page.total == 1
    assert not hasattr(BeamService(), "delete")

    empty_page = BeamService().list(BeamFilter(statuses=[]))
    assert empty_page.items == []
    assert empty_page.total == 0


def test_beam_position_assignment_move_release_and_conflicts(domain_prefix):
    area = _create_area(domain_prefix)
    beam_type = _create_type(domain_prefix)
    pos_a = _create_position(domain_prefix, area.area_code, "POS_A")
    pos_b = _create_position(domain_prefix, area.area_code, "POS_B")
    beam_a = _create_beam(domain_prefix, beam_type.type_code, "BEAM_A")
    beam_b = _create_beam(domain_prefix, beam_type.type_code, "BEAM_B")

    assigned = BeamService().assign_position(
        beam_a.beam_code,
        BeamPositionCommand(position_code=pos_a.position_code),
    )
    assert assigned.current_position_code == pos_a.position_code
    assert BeamService().assign_position(
        beam_a.beam_code,
        BeamPositionCommand(position_code=pos_a.position_code),
    ).current_position_code == pos_a.position_code

    with pytest.raises(BeamAlreadyPositionedError):
        BeamService().assign_position(
            beam_a.beam_code,
            BeamPositionCommand(position_code=pos_b.position_code),
        )
    with pytest.raises(PositionOccupiedError):
        BeamService().assign_position(
            beam_b.beam_code,
            BeamPositionCommand(position_code=pos_a.position_code),
        )

    moved = BeamService().move_beam(
        beam_a.beam_code,
        BeamPositionCommand(position_code=pos_b.position_code),
    )
    assert moved.current_position_code == pos_b.position_code
    assert BeamPositionService().get(pos_a.id).is_occupied is False

    released = BeamService().release_position(beam_a.beam_code)
    assert released.current_position_code is None
    assert BeamService().release_position(beam_a.beam_code).is_positioned is False


def test_failed_move_keeps_original_position(domain_prefix):
    area = _create_area(domain_prefix)
    beam_type = _create_type(domain_prefix)
    pos_a = _create_position(domain_prefix, area.area_code, "POS_A")
    pos_b = _create_position(domain_prefix, area.area_code, "POS_B")
    beam_a = _create_beam(domain_prefix, beam_type.type_code, "BEAM_A")
    beam_b = _create_beam(domain_prefix, beam_type.type_code, "BEAM_B")
    BeamService().assign_position(
        beam_a.beam_code,
        BeamPositionCommand(position_code=pos_a.position_code),
    )
    BeamService().assign_position(
        beam_b.beam_code,
        BeamPositionCommand(position_code=pos_b.position_code),
    )

    with pytest.raises(PositionOccupiedError):
        BeamService().move_beam(
            beam_a.beam_code,
            BeamPositionCommand(position_code=pos_b.position_code),
        )

    assert BeamService().get(beam_a.id).current_position_code == pos_a.position_code


def test_occupied_or_inactive_position_rules(domain_prefix):
    area = _create_area(domain_prefix)
    beam_type = _create_type(domain_prefix)
    position = _create_position(domain_prefix, area.area_code, "POS")
    beam = _create_beam(domain_prefix, beam_type.type_code, "BEAM")
    BeamService().assign_position(
        beam.beam_code,
        BeamPositionCommand(position_code=position.position_code),
    )

    with pytest.raises(ResourceConflictError):
        BeamPositionService().set_active(position.id, is_active=False)

    BeamService().release_position(beam.beam_code)
    BeamPositionService().set_active(position.id, is_active=False)
    with pytest.raises(InactiveResourceError):
        BeamService().assign_position(
            beam.beam_code,
            BeamPositionCommand(position_code=position.position_code),
        )


def test_missing_position_is_reported_by_public_exception(domain_prefix):
    beam_type = _create_type(domain_prefix)
    beam = _create_beam(domain_prefix, beam_type.type_code, "BEAM")
    with pytest.raises(BeamPositionNotFoundError):
        BeamService().assign_position(
            beam.beam_code,
            BeamPositionCommand(
                position_code=f"{domain_prefix}_MISSING_POSITION"
            ),
        )


def test_concurrent_position_assignment_allows_only_one_beam(domain_prefix):
    area = _create_area(domain_prefix)
    beam_type = _create_type(domain_prefix)
    position = _create_position(domain_prefix, area.area_code, "POS")
    beam_a = _create_beam(domain_prefix, beam_type.type_code, "BEAM_A")
    beam_b = _create_beam(domain_prefix, beam_type.type_code, "BEAM_B")
    barrier = Barrier(2)

    def assign(beam_code: str):
        barrier.wait()
        try:
            return BeamService().assign_position(
                beam_code,
                BeamPositionCommand(position_code=position.position_code),
            ).beam_code
        except PositionOccupiedError:
            return "occupied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(assign, (beam_a.beam_code, beam_b.beam_code))
        )

    assert results.count("occupied") == 1
    assert len([result for result in results if result != "occupied"]) == 1
    assert BeamPositionService().get(position.id).is_occupied is True


def test_position_creation_blocks_concurrent_area_deactivation(
    domain_prefix,
    monkeypatch,
):
    area = _create_area(domain_prefix)
    create_reached_write = Event()
    allow_create = Event()
    original_create = beam_position_service_module.create_beam_position

    def delayed_create(*args, **kwargs):
        create_reached_write.set()
        if not allow_create.wait(timeout=5):
            raise RuntimeError("测试未能继续创建梁位")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        beam_position_service_module,
        "create_beam_position",
        delayed_create,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        create_future = executor.submit(
            _create_position,
            domain_prefix,
            area.area_code,
            "POS_LOCKED_AREA",
        )
        assert create_reached_write.wait(timeout=5)
        deactivate_future = executor.submit(
            YardAreaService().set_active,
            area.id,
            is_active=False,
        )

        try:
            with pytest.raises(FutureTimeoutError):
                deactivate_future.result(timeout=0.2)
        finally:
            allow_create.set()

        created = create_future.result(timeout=5)
        with pytest.raises(ResourceConflictError):
            deactivate_future.result(timeout=5)

    assert created.is_active is True
    assert YardAreaService().get(area.id).is_active is True
