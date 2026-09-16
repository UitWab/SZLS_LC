from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event

from backend_db.database.mysql import SessionLocal, engine
from backend_db.exceptions import (
    BeamProcessExecutionNotFoundError,
    BeamQualityInspectionNotFoundError,
    InactiveResourceError,
    ProcessDefinitionNotFoundError,
    ResourceConflictError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    Beam,
    BeamLifecycleEvent,
    BeamProcessExecution,
    BeamQualityInspection,
    BeamQualityInspectionItem,
    BeamType,
    ProcessDefinition,
    Project,
)
from backend_db.schemas import (
    BeamCreate,
    BeamProcessExecutionCreate,
    BeamProcessExecutionVoid,
    BeamProcessResult,
    BeamQualityInspectionCreate,
    BeamQualityInspectionFilter,
    BeamQualityInspectionItemCreate,
    BeamQualityInspectionSortField,
    BeamQualityInspectionVoid,
    BeamQualityItemResult,
    BeamQualityResult,
    BeamTypeCreate,
    PageRequest,
    ProcessDefinitionCreate,
    ProcessDefinitionUpdate,
    ProjectCreate,
    RecordSource,
    SortOrder,
)


BASE_TIME = datetime(2026, 9, 16, 2, 0, 0)


def _setup(suffix: str, *, beam_count: int = 1):
    services = create_database_services()
    project_code = f"V7_PROJECT_{suffix}"
    type_code = f"V7_TYPE_{suffix}"
    process_code = f"V7_PROCESS_{suffix}"
    beam_codes = [f"V7_BEAM_{suffix}_{index}" for index in range(beam_count)]
    services.projects.create(ProjectCreate(
        project_code=project_code, project_name="V7测试项目"
    ))
    services.beam_types.create(BeamTypeCreate(
        type_code=type_code,
        type_name="V7测试梁型",
        project_code=project_code,
    ))
    for beam_code in beam_codes:
        services.beams.create(BeamCreate(
            beam_code=beam_code,
            beam_type_code=type_code,
            project_code=project_code,
        ))
    services.processes.create(ProcessDefinitionCreate(
        process_code=process_code,
        process_name="V7测试工序",
        project_code=project_code,
    ))
    return services, project_code, beam_codes, process_code


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        inspections = session.query(BeamQualityInspection).filter(
            BeamQualityInspection.inspection_code.contains(suffix)
        ).all()
        inspection_ids = [item.id for item in inspections]
        if inspection_ids:
            session.execute(delete(BeamQualityInspectionItem).where(
                BeamQualityInspectionItem.inspection_id.in_(inspection_ids)
            ))
            for inspection in inspections:
                inspection.previous_inspection_id = None
            session.flush()
            session.execute(delete(BeamQualityInspection).where(
                BeamQualityInspection.id.in_(inspection_ids)
            ))
        executions = session.query(BeamProcessExecution).filter(
            BeamProcessExecution.execution_code.contains(suffix)
        ).all()
        for execution in executions:
            execution.supersedes_execution_id = None
        session.flush()
        session.execute(delete(BeamProcessExecution).where(
            BeamProcessExecution.execution_code.contains(suffix)
        ))
        beams = session.query(Beam).filter(Beam.beam_code.contains(suffix)).all()
        beam_ids = [item.id for item in beams]
        if beam_ids:
            session.execute(delete(BeamLifecycleEvent).where(
                BeamLifecycleEvent.beam_id.in_(beam_ids)
            ))
            session.execute(delete(Beam).where(Beam.id.in_(beam_ids)))
        session.execute(delete(ProcessDefinition).where(
            ProcessDefinition.process_code.contains(suffix)
        ))
        session.execute(delete(BeamType).where(BeamType.type_code.contains(suffix)))
        session.execute(delete(Project).where(Project.project_code.contains(suffix)))


def _items():
    return [
        BeamQualityInspectionItemCreate(
            item_code="DIMENSION",
            item_name="外形尺寸",
            observed_value="合格",
            result_code=BeamQualityItemResult.PASS,
        ),
        BeamQualityInspectionItemCreate(
            item_code="SURFACE",
            item_name="表面质量",
            requirement_text="无明显缺陷",
            result_code=BeamQualityItemResult.PASS,
        ),
    ]


def _inspection_data(
    suffix: str,
    project_code: str | None,
    beam_code: str,
    **changes,
):
    values = {
        "inspection_code": f"V7_INSPECTION_{suffix}",
        "project_code": project_code,
        "beam_code": beam_code,
        "inspection_type_code": "FINAL_CHECK",
        "result_code": BeamQualityResult.PASS,
        "inspected_at": BASE_TIME,
        "actor_name": "质量检查员",
        "source": RecordSource.MANUAL,
        "summary": "检查通过",
        "items": _items(),
    }
    values.update(changes)
    return BeamQualityInspectionCreate(**values)


def _execution_data(suffix, project_code, beam_code, process_code):
    return BeamProcessExecutionCreate(
        execution_code=f"V7_EXECUTION_{suffix}",
        project_code=project_code,
        beam_code=beam_code,
        process_code=process_code,
        result_code=BeamProcessResult.SUCCESS,
        started_at=BASE_TIME - timedelta(hours=1),
        finished_at=BASE_TIME - timedelta(minutes=30),
        actor_name="生产人员",
    )


def test_v7_schema_normalizes_time_and_enforces_item_consistency():
    local_time = BASE_TIME.replace(tzinfo=timezone(timedelta(hours=8)))
    data = BeamQualityInspectionCreate(
        inspection_code="INSPECTION",
        beam_code="BEAM",
        inspection_type_code="CHECK",
        result_code=BeamQualityResult.PASS,
        inspected_at=local_time,
        actor_name=" 检查员 ",
    )
    assert data.inspected_at == BASE_TIME - timedelta(hours=8)
    assert data.actor_name == "检查员"
    with pytest.raises(ValidationError):
        BeamQualityInspectionCreate(
            inspection_code="INSPECTION",
            beam_code="BEAM",
            inspection_type_code="CHECK",
            result_code=BeamQualityResult.PASS,
            inspected_at=BASE_TIME,
            actor_name="检查员",
            items=[BeamQualityInspectionItemCreate(
                item_code="ITEM",
                item_name="检查项",
                result_code=BeamQualityItemResult.FAIL,
            )],
        )
    with pytest.raises(ValidationError):
        _inspection_data(
            "DUPLICATE",
            None,
            "BEAM",
            items=[_items()[0], _items()[0]],
        )


def test_v7_records_items_and_allows_summary_only():
    suffix = uuid4().hex[:8]
    services, project, beams, process = _setup(suffix)
    try:
        before_beam = services.beams.get_by_code(beams[0], project_code=project)
        with SessionLocal() as session:
            beam_id = session.query(Beam.id).filter_by(
                beam_code=beams[0]
            ).scalar()
            before_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        detailed = services.quality_records.record(_inspection_data(
            suffix, project, beams[0], process_code=process
        ))
        summary_only = services.quality_records.record(_inspection_data(
            suffix,
            project,
            beams[0],
            inspection_code=f"V7_EMPTY_{suffix}",
            items=[],
            result_code=BeamQualityResult.FAIL,
        ))
        assert detailed.project_code == project
        assert detailed.process_code == process
        assert [item.item_code for item in detailed.items] == [
            "DIMENSION", "SURFACE"
        ]
        assert summary_only.items == []
        assert services.quality_records.get(
            detailed.inspection_code, project_code=project
        ) == detailed
        after_beam = services.beams.get_by_code(beams[0], project_code=project)
        with SessionLocal() as session:
            after_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        assert after_beam.status == before_beam.status
        assert after_events == before_events
    finally:
        _cleanup(suffix)


def test_v7_execution_link_derives_process_and_rejects_invalid_links():
    suffix = uuid4().hex[:8]
    services, project, beams, process = _setup(suffix, beam_count=2)
    try:
        execution = services.process_records.record(
            _execution_data(suffix, project, beams[0], process)
        )
        inspection = services.quality_records.record(_inspection_data(
            suffix,
            project,
            beams[0],
            process_execution_code=execution.execution_code,
        ))
        assert inspection.process_code == process
        assert inspection.process_execution_code == execution.execution_code

        with pytest.raises(ResourceConflictError):
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[1],
                inspection_code=f"V7_WRONG_BEAM_{suffix}",
                process_execution_code=execution.execution_code,
            ))
        services.process_records.void(
            execution.execution_code,
            BeamProcessExecutionVoid(
                voided_by_name="纠错人员", void_reason="执行记录错误"
            ),
            project_code=project,
        )
        assert services.quality_records.record(_inspection_data(
            suffix,
            project,
            beams[0],
            process_execution_code=execution.execution_code,
        )) == inspection
        with pytest.raises(ResourceConflictError):
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[0],
                inspection_code=f"V7_VOID_EXEC_{suffix}",
                process_execution_code=execution.execution_code,
            ))
        with pytest.raises(BeamProcessExecutionNotFoundError):
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[0],
                inspection_code=f"V7_MISSING_EXEC_{suffix}",
                process_execution_code=f"V7_MISSING_{suffix}",
            ))
    finally:
        _cleanup(suffix)


def test_v7_reinspection_requires_same_project_and_beam_but_allows_branches():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix, beam_count=2)
    try:
        original = services.quality_records.record(_inspection_data(
            suffix,
            project,
            beams[0],
            result_code=BeamQualityResult.FAIL,
            items=[],
        ))
        branches = [
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[0],
                inspection_code=f"V7_RECHECK_{index}_{suffix}",
                previous_inspection_code=original.inspection_code,
            ))
            for index in range(2)
        ]
        assert all(
            item.previous_inspection_code == original.inspection_code
            for item in branches
        )
        with pytest.raises(ResourceConflictError):
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[1],
                inspection_code=f"V7_WRONG_RECHECK_{suffix}",
                previous_inspection_code=original.inspection_code,
            ))
        with pytest.raises(BeamQualityInspectionNotFoundError):
            services.quality_records.get(original.inspection_code)
    finally:
        _cleanup(suffix)


def test_v7_idempotency_ignores_item_order_and_rejects_changed_content():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)
    data = _inspection_data(
        suffix,
        project,
        beams[0],
        source=RecordSource.IMPORT,
        external_record_id=f"V7_EXTERNAL_{suffix}",
        items=[
            BeamQualityInspectionItemCreate(
                item_code="Z",
                item_name="大写编码检查项",
                result_code=BeamQualityItemResult.PASS,
            ),
            BeamQualityInspectionItemCreate(
                item_code="a",
                item_name="小写编码检查项",
                result_code=BeamQualityItemResult.PASS,
            ),
        ],
    )
    try:
        first = services.quality_records.record(data)
        reordered = data.model_copy(update={"items": list(reversed(data.items))})
        assert services.quality_records.record(reordered) == first
        with pytest.raises(ResourceConflictError):
            services.quality_records.record(data.model_copy(update={
                "inspection_code": f"V7_CHANGED_{suffix}",
                "summary": "不同内容",
            }))
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: services.quality_records.record(data), range(2)
            ))
        assert results[0].id == results[1].id
        with SessionLocal() as session:
            assert session.query(BeamQualityInspection).filter_by(
                external_record_id=f"V7_EXTERNAL_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)


def test_v7_item_codes_are_case_sensitive_exact_identifiers():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)
    data = _inspection_data(
        suffix,
        project,
        beams[0],
        items=[
            BeamQualityInspectionItemCreate(
                item_code="ITEM",
                item_name="大写编码检查项",
                result_code=BeamQualityItemResult.PASS,
            ),
            BeamQualityInspectionItemCreate(
                item_code="item",
                item_name="小写编码检查项",
                result_code=BeamQualityItemResult.PASS,
            ),
        ],
    )
    try:
        created = services.quality_records.record(data)
        assert {item.item_code for item in created.items} == {"ITEM", "item"}
        assert services.quality_records.record(data) == created
    finally:
        _cleanup(suffix)


def test_v7_concurrent_first_record_creates_one_main_and_one_item_set():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)
    data = _inspection_data(
        suffix,
        project,
        beams[0],
        source=RecordSource.SYSTEM,
        external_record_id=f"V7_CONCURRENT_{suffix}",
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: services.quality_records.record(data), range(2)
            ))
        assert results[0].id == results[1].id
        with SessionLocal() as session:
            stored = session.query(BeamQualityInspection).filter_by(
                external_record_id=f"V7_CONCURRENT_{suffix}"
            ).one()
            assert session.query(BeamQualityInspectionItem).filter_by(
                inspection_id=stored.id
            ).count() == len(data.items)
    finally:
        _cleanup(suffix)


def test_v7_idempotent_retry_survives_inactive_resources():
    suffix = uuid4().hex[:8]
    services, project, beams, process = _setup(suffix)
    data = _inspection_data(
        suffix, project, beams[0], process_code=process
    )
    try:
        first = services.quality_records.record(data)
        process_item = services.processes.get_by_code(process, project_code=project)
        services.processes.set_active(
            process_item.id, is_active=False, project_code=project
        )
        assert services.quality_records.record(data) == first
        with pytest.raises(InactiveResourceError):
            services.quality_records.record(data.model_copy(update={
                "inspection_code": f"V7_NEW_INACTIVE_{suffix}",
            }))
    finally:
        _cleanup(suffix)


def test_v7_void_is_idempotent_and_items_remain_immutable():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)
    try:
        record = services.quality_records.record(
            _inspection_data(suffix, project, beams[0])
        )
        first = services.quality_records.void(
            record.inspection_code,
            BeamQualityInspectionVoid(
                voided_by_name="质量负责人", void_reason="录入错误"
            ),
            project_code=project,
        )
        repeated = services.quality_records.void(
            record.inspection_code,
            BeamQualityInspectionVoid(
                voided_by_name="其他人员", void_reason="不能覆盖"
            ),
            project_code=project,
        )
        assert first.is_voided is True
        assert repeated.void_reason == "录入错误"
        assert repeated.voided_at == first.voided_at
        assert repeated.items == record.items
    finally:
        _cleanup(suffix)


def test_v7_concurrent_void_preserves_first_result():
    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)
    try:
        record = services.quality_records.record(
            _inspection_data(suffix, project, beams[0])
        )

        def void_with(index: int):
            return services.quality_records.void(
                record.inspection_code,
                BeamQualityInspectionVoid(
                    voided_by_name=f"作废人{index}",
                    void_reason=f"作废原因{index}",
                ),
                project_code=project,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(void_with, range(2)))
        assert results[0].voided_at == results[1].voided_at
        assert results[0].voided_by_name == results[1].voided_by_name
        assert results[0].void_reason == results[1].void_reason
    finally:
        _cleanup(suffix)


def test_v7_filters_and_pages_without_expanding_items():
    suffix = uuid4().hex[:8]
    services, project, beams, process = _setup(suffix)
    try:
        created = [
            services.quality_records.record(_inspection_data(
                suffix,
                project,
                beams[0],
                inspection_code=f"V7_PAGE_{index}_{suffix}",
                process_code=process,
                result_code=(
                    BeamQualityResult.PASS
                    if index != 1
                    else BeamQualityResult.FAIL
                ),
                items=[] if index == 1 else _items(),
                inspected_at=BASE_TIME + timedelta(hours=index),
            ))
            for index in range(3)
        ]
        statements = []

        def record_statement(_conn, _cursor, statement, *_args):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            page = services.quality_records.list(
                BeamQualityInspectionFilter(
                    project_code=project,
                    process_code=process,
                    result_codes=[BeamQualityResult.PASS],
                    keyword=suffix,
                ),
                PageRequest(page_size=1, include_total=False),
                sort_by=BeamQualityInspectionSortField.INSPECTED_AT,
                sort_order=SortOrder.DESC,
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
        assert [item.id for item in page.items] == [created[2].id]
        assert page.total is None
        assert page.has_next is True
        assert not hasattr(page.items[0], "items")
        assert not any(
            "beam_quality_inspection_item" in statement.lower()
            for statement in statements
        )
    finally:
        _cleanup(suffix)


def test_v7_process_project_is_immutable_after_direct_quality_reference():
    suffix = uuid4().hex[:8]
    services, project, beams, process_code = _setup(suffix)
    other_project = f"V7_OTHER_{suffix}"
    try:
        services.projects.create(ProjectCreate(
            project_code=other_project, project_name="其他项目"
        ))
        services.quality_records.record(_inspection_data(
            suffix, project, beams[0], process_code=process_code
        ))
        process = services.processes.get_by_code(
            process_code, project_code=project
        )
        with pytest.raises(ResourceConflictError):
            services.processes.update(
                process.id,
                ProcessDefinitionUpdate(project_code=other_project),
                project_code=project,
            )
    finally:
        _cleanup(suffix)


def test_v7_global_beam_accepts_only_global_process():
    suffix = uuid4().hex[:8]
    services, project, _, project_process = _setup(suffix, beam_count=0)
    global_type = f"V7_GLOBAL_TYPE_{suffix}"
    global_beam = f"V7_GLOBAL_BEAM_{suffix}"
    global_process = f"V7_GLOBAL_PROCESS_{suffix}"
    try:
        services.beam_types.create(BeamTypeCreate(
            type_code=global_type, type_name="全局梁型"
        ))
        services.beams.create(BeamCreate(
            beam_code=global_beam, beam_type_code=global_type
        ))
        services.processes.create(ProcessDefinitionCreate(
            process_code=global_process, process_name="全局工序"
        ))
        record = services.quality_records.record(_inspection_data(
            suffix,
            None,
            global_beam,
            process_code=global_process,
        ))
        assert record.project_code is None
        assert record.process_code == global_process
        with pytest.raises(BeamQualityInspectionNotFoundError):
            services.quality_records.get(
                record.inspection_code, project_code=project
            )
        with pytest.raises(ProcessDefinitionNotFoundError):
            services.quality_records.record(_inspection_data(
                suffix,
                None,
                global_beam,
                inspection_code=f"V7_INVALID_GLOBAL_{suffix}",
                process_code=project_process,
            ))
    finally:
        _cleanup(suffix)


def test_v7_record_rolls_back_main_and_items_if_conversion_fails(monkeypatch):
    from backend_db.services import beam_quality_inspection as service_module

    suffix = uuid4().hex[:8]
    services, project, beams, _ = _setup(suffix)

    def fail_after_flush(*_args):
        raise RuntimeError("forced failure after flush")

    try:
        monkeypatch.setattr(service_module, "_to_read", fail_after_flush)
        with pytest.raises(RuntimeError, match="forced failure"):
            services.quality_records.record(
                _inspection_data(suffix, project, beams[0])
            )
        with SessionLocal() as session:
            assert session.query(BeamQualityInspection).filter_by(
                inspection_code=f"V7_INSPECTION_{suffix}"
            ).count() == 0
            assert session.query(BeamQualityInspectionItem).join(
                BeamQualityInspection
            ).filter(
                BeamQualityInspection.inspection_code
                == f"V7_INSPECTION_{suffix}"
            ).count() == 0
    finally:
        _cleanup(suffix)


def test_v7_public_service_has_no_workflow_or_delete_methods():
    service = create_database_services().quality_records
    for method in ("update", "delete", "approve", "release", "upload"):
        assert not hasattr(service, method)
