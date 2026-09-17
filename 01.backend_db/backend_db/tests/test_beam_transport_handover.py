from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamTransportHandoverNotFoundError,
    InactiveResourceError,
    ResourceConflictError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    Beam,
    BeamLifecycleEvent,
    BeamTransportHandover,
    BeamType,
    Project,
)
from backend_db.schemas import (
    BeamCreate,
    BeamTransportHandoverCreate,
    BeamTransportHandoverFilter,
    BeamTransportHandoverSortField,
    BeamTransportHandoverVoid,
    BeamTypeCreate,
    PageRequest,
    ProjectCreate,
    RecordSource,
    SortOrder,
    TransportHandoverResult,
    TransportHandoverType,
)


BASE_TIME = datetime(2026, 9, 17, 2, 0, 0)


def _setup(suffix: str, *, beam_count: int = 1):
    services = create_database_services()
    project_code = f"V8_PROJECT_{suffix}"
    type_code = f"V8_TYPE_{suffix}"
    beam_codes = [f"V8_BEAM_{suffix}_{index}" for index in range(beam_count)]
    services.projects.create(ProjectCreate(
        project_code=project_code, project_name="V8测试项目"
    ))
    services.beam_types.create(BeamTypeCreate(
        type_code=type_code,
        type_name="V8测试梁型",
        project_code=project_code,
    ))
    for beam_code in beam_codes:
        services.beams.create(BeamCreate(
            beam_code=beam_code,
            beam_type_code=type_code,
            project_code=project_code,
        ))
    return services, project_code, beam_codes


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        session.execute(delete(BeamTransportHandover).where(
            BeamTransportHandover.handover_code.contains(suffix)
        ))
        beams = session.query(Beam).filter(Beam.beam_code.contains(suffix)).all()
        beam_ids = [item.id for item in beams]
        if beam_ids:
            session.execute(delete(BeamLifecycleEvent).where(
                BeamLifecycleEvent.beam_id.in_(beam_ids)
            ))
            session.execute(delete(Beam).where(Beam.id.in_(beam_ids)))
        session.execute(delete(BeamType).where(BeamType.type_code.contains(suffix)))
        session.execute(delete(Project).where(Project.project_code.contains(suffix)))


def _handover_data(
    suffix: str,
    project_code: str | None,
    beam_code: str,
    **changes,
):
    values = {
        "handover_code": f"V8_HANDOVER_{suffix}",
        "project_code": project_code,
        "beam_code": beam_code,
        "handover_type": TransportHandoverType.TRANSFER,
        "result_code": TransportHandoverResult.ACCEPTED,
        "from_location": "预制场",
        "to_location": "临时堆场",
        "carrier_name": "测试承运单位",
        "vehicle_no": f"CAR-{suffix}",
        "sender_name": "移交人",
        "receiver_name": "接收人",
        "occurred_at": BASE_TIME,
        "actor_name": "运输记录员",
        "source": RecordSource.MANUAL,
        "remark": "交接正常",
    }
    values.update(changes)
    return BeamTransportHandoverCreate(**values)


def test_v8_schema_normalizes_time_and_validates_type_locations():
    local_time = BASE_TIME.replace(tzinfo=timezone(timedelta(hours=8)))
    data = BeamTransportHandoverCreate(
        handover_code="HANDOVER",
        beam_code="BEAM",
        handover_type=TransportHandoverType.OUTBOUND,
        result_code=TransportHandoverResult.ACCEPTED,
        to_location=" 目的地 ",
        occurred_at=local_time,
        actor_name=" 记录员 ",
    )
    assert data.occurred_at == BASE_TIME - timedelta(hours=8)
    assert data.to_location == "目的地"
    assert data.actor_name == "记录员"

    invalid_values = (
        {"handover_type": TransportHandoverType.OUTBOUND},
        {"handover_type": TransportHandoverType.ARRIVAL},
        {
            "handover_type": TransportHandoverType.TRANSFER,
            "from_location": "起点",
        },
    )
    for changes in invalid_values:
        with pytest.raises(ValidationError):
            BeamTransportHandoverCreate(
                handover_code="HANDOVER",
                beam_code="BEAM",
                result_code=TransportHandoverResult.REJECTED,
                occurred_at=BASE_TIME,
                actor_name="记录员",
                **changes,
            )
    with pytest.raises(ValidationError):
        BeamTransportHandoverCreate(
            handover_code="HANDOVER",
            beam_code="BEAM",
            handover_type=TransportHandoverType.OUTBOUND,
            result_code=TransportHandoverResult.ACCEPTED,
            to_location="目的地",
            occurred_at=BASE_TIME,
        )
    with pytest.raises(ValidationError):
        BeamTransportHandoverFilter(
            occurred_at_from=BASE_TIME,
            occurred_at_to=BASE_TIME - timedelta(seconds=1),
        )


def test_v8_records_all_handover_types_without_beam_side_effects():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    try:
        before_beam = services.beams.get_by_code(beams[0], project_code=project)
        with SessionLocal() as session:
            beam_id = session.query(Beam.id).filter_by(beam_code=beams[0]).scalar()
            before_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        records = [
            services.transport_records.record(_handover_data(
                suffix,
                project,
                beams[0],
                handover_code=f"V8_OUTBOUND_{suffix}",
                handover_type=TransportHandoverType.OUTBOUND,
                from_location=None,
                to_location="工地",
            )),
            services.transport_records.record(_handover_data(
                suffix,
                project,
                beams[0],
                handover_code=f"V8_TRANSFER_{suffix}",
            )),
            services.transport_records.record(_handover_data(
                suffix,
                project,
                beams[0],
                handover_code=f"V8_ARRIVAL_{suffix}",
                handover_type=TransportHandoverType.ARRIVAL,
                from_location="临时堆场",
                to_location=None,
                result_code=TransportHandoverResult.REJECTED,
            )),
        ]
        assert {item.handover_type for item in records} == set(TransportHandoverType)
        assert records[2].result_code == TransportHandoverResult.REJECTED
        assert services.transport_records.get(
            records[0].handover_code, project_code=project
        ) == records[0]
        after_beam = services.beams.get_by_code(beams[0], project_code=project)
        with SessionLocal() as session:
            after_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        assert after_beam.status == before_beam.status
        assert after_events == before_events
    finally:
        _cleanup(suffix)


def test_v8_project_scope_and_global_beam_are_isolated():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    global_type = f"V8_GLOBAL_TYPE_{suffix}"
    global_beam = f"V8_GLOBAL_BEAM_{suffix}"
    try:
        project_record = services.transport_records.record(
            _handover_data(suffix, project, beams[0])
        )
        with pytest.raises(BeamTransportHandoverNotFoundError):
            services.transport_records.get(project_record.handover_code)
        with pytest.raises(BeamNotFoundError):
            services.transport_records.record(_handover_data(
                suffix,
                None,
                beams[0],
                handover_code=f"V8_WRONG_SCOPE_{suffix}",
            ))

        services.beam_types.create(BeamTypeCreate(
            type_code=global_type, type_name="全局运输梁型"
        ))
        services.beams.create(BeamCreate(
            beam_code=global_beam, beam_type_code=global_type
        ))
        global_record = services.transport_records.record(_handover_data(
            suffix,
            None,
            global_beam,
            handover_code=f"V8_GLOBAL_HANDOVER_{suffix}",
        ))
        assert global_record.project_code is None
        assert services.transport_records.get(global_record.handover_code) == global_record
    finally:
        _cleanup(suffix)


def test_v8_external_idempotency_and_concurrent_first_record():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    data = _handover_data(
        suffix,
        project,
        beams[0],
        source=RecordSource.IMPORT,
        external_record_id=f"V8_EXTERNAL_{suffix}",
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: services.transport_records.record(data), range(2)
            ))
        assert results[0].id == results[1].id
        assert services.transport_records.record(data) == results[0]
        with pytest.raises(ResourceConflictError):
            services.transport_records.record(data.model_copy(update={
                "handover_code": f"V8_CHANGED_{suffix}",
                "remark": "不同内容",
            }))
        with SessionLocal() as session:
            assert session.query(BeamTransportHandover).filter_by(
                external_record_id=f"V8_EXTERNAL_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)


def test_v8_idempotent_retry_survives_inactive_project():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    data = _handover_data(suffix, project, beams[0])
    try:
        first = services.transport_records.record(data)
        project_item = services.projects.get_by_code(project)
        services.projects.set_active(project_item.id, is_active=False)
        assert services.transport_records.record(data) == first
        with pytest.raises(InactiveResourceError):
            services.transport_records.record(data.model_copy(update={
                "handover_code": f"V8_NEW_INACTIVE_{suffix}",
            }))
    finally:
        _cleanup(suffix)


def test_v8_void_is_idempotent_and_concurrent_safe():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    try:
        record = services.transport_records.record(
            _handover_data(suffix, project, beams[0])
        )

        def void_with(index: int):
            return services.transport_records.void(
                record.handover_code,
                BeamTransportHandoverVoid(
                    voided_by_name=f"作废人{index}",
                    void_reason=f"作废原因{index}",
                ),
                project_code=project,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(void_with, range(2)))
        assert results[0].voided_at == results[1].voided_at
        assert results[0].void_reason == results[1].void_reason
        repeated = services.transport_records.void(
            record.handover_code,
            BeamTransportHandoverVoid(
                voided_by_name="其他人", void_reason="不应覆盖"
            ),
            project_code=project,
        )
        assert repeated.void_reason == results[0].void_reason
    finally:
        _cleanup(suffix)


def test_v8_filters_and_pages_are_stable():
    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)
    try:
        created = [
            services.transport_records.record(_handover_data(
                suffix,
                project,
                beams[0],
                handover_code=f"V8_PAGE_{index}_{suffix}",
                result_code=(
                    TransportHandoverResult.REJECTED
                    if index == 1
                    else TransportHandoverResult.ACCEPTED
                ),
                occurred_at=BASE_TIME + timedelta(hours=index),
            ))
            for index in range(3)
        ]
        page = services.transport_records.list(
            BeamTransportHandoverFilter(
                project_code=project,
                beam_code=beams[0],
                result_codes=[TransportHandoverResult.ACCEPTED],
                vehicle_no=f"CAR-{suffix}",
                carrier_name="测试承运单位",
                keyword=suffix,
            ),
            PageRequest(page_size=1, include_total=False),
            sort_by=BeamTransportHandoverSortField.OCCURRED_AT,
            sort_order=SortOrder.DESC,
        )
        assert [item.id for item in page.items] == [created[2].id]
        assert page.total is None
        assert page.has_next is True
    finally:
        _cleanup(suffix)


def test_v8_record_rolls_back_if_conversion_fails(monkeypatch):
    from backend_db.services import beam_transport_handover as service_module

    suffix = uuid4().hex[:8]
    services, project, beams = _setup(suffix)

    def fail_after_flush(*_args):
        raise RuntimeError("forced failure after flush")

    try:
        monkeypatch.setattr(service_module, "_to_read", fail_after_flush)
        with pytest.raises(RuntimeError, match="forced failure"):
            services.transport_records.record(
                _handover_data(suffix, project, beams[0])
            )
        with SessionLocal() as session:
            assert session.query(BeamTransportHandover).filter_by(
                handover_code=f"V8_HANDOVER_{suffix}"
            ).count() == 0
    finally:
        _cleanup(suffix)


def test_v8_public_service_has_no_workflow_or_delete_methods():
    service = create_database_services().transport_records
    for method in (
        "update",
        "delete",
        "dispatch",
        "complete",
        "track",
        "upload",
    ):
        assert not hasattr(service, method)
