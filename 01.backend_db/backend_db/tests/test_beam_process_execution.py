from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamProcessExecutionNotFoundError,
    InactiveResourceError,
    ProcessDefinitionNotFoundError,
    ResourceConflictError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    Beam,
    BeamLifecycleEvent,
    BeamProcessExecution,
    BeamType,
    ProcessDefinition,
    Project,
    UserCredential,
    AppUser,
)
from backend_db.schemas import (
    BeamCreate,
    BeamProcessExecutionCreate,
    BeamProcessExecutionFilter,
    BeamProcessExecutionSortField,
    BeamProcessExecutionVoid,
    BeamProcessResult,
    BeamTypeCreate,
    PageRequest,
    ProcessDefinitionCreate,
    ProcessDefinitionUpdate,
    ProjectCreate,
    RecordSource,
    SortOrder,
    UserCreate,
)


BASE_TIME = datetime(2026, 9, 15, 1, 0, 0)


def _hash(label: str) -> str:
    return f"$argon2id$v=19$m=65536,t=3,p=4${label}_hash_value"


def _setup(suffix: str):
    services = create_database_services()
    project_code = f"V6_PROJECT_{suffix}"
    beam_type_code = f"V6_TYPE_{suffix}"
    beam_code = f"V6_BEAM_{suffix}"
    process_code = f"V6_PROCESS_{suffix}"
    global_process_code = f"V6_GLOBAL_PROCESS_{suffix}"
    services.projects.create(ProjectCreate(
        project_code=project_code, project_name="V6测试项目"
    ))
    services.beam_types.create(BeamTypeCreate(
        type_code=beam_type_code,
        type_name="V6测试梁型",
        project_code=project_code,
    ))
    services.beams.create(BeamCreate(
        beam_code=beam_code,
        beam_type_code=beam_type_code,
        project_code=project_code,
    ))
    services.processes.create(ProcessDefinitionCreate(
        process_code=process_code,
        process_name="项目工序",
        project_code=project_code,
    ))
    services.processes.create(ProcessDefinitionCreate(
        process_code=global_process_code,
        process_name="通用工序",
    ))
    return services, project_code, beam_code, process_code, global_process_code


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        executions = session.query(BeamProcessExecution).filter(
            BeamProcessExecution.execution_code.contains(suffix)
        ).all()
        for item in executions:
            item.supersedes_execution_id = None
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
        users = session.query(AppUser).filter(AppUser.username.contains(suffix)).all()
        user_ids = [item.id for item in users]
        if user_ids:
            session.execute(delete(UserCredential).where(
                UserCredential.user_id.in_(user_ids)
            ))
            session.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))
        session.execute(delete(Project).where(Project.project_code.contains(suffix)))


def _create_data(
    suffix: str,
    project_code: str | None,
    beam_code: str,
    process_code: str,
    **changes,
) -> BeamProcessExecutionCreate:
    values = {
        "execution_code": f"V6_EXEC_{suffix}",
        "project_code": project_code,
        "beam_code": beam_code,
        "process_code": process_code,
        "result_code": BeamProcessResult.SUCCESS,
        "started_at": BASE_TIME,
        "finished_at": BASE_TIME + timedelta(minutes=30),
        "actor_name": "外部操作人",
        "source": RecordSource.MANUAL,
        "remark": f"执行说明 {suffix}",
    }
    values.update(changes)
    return BeamProcessExecutionCreate(**values)


def test_v6_schema_normalizes_time_and_rejects_invalid_records():
    local_time = BASE_TIME.replace(tzinfo=timezone(timedelta(hours=8)))
    data = BeamProcessExecutionCreate(
        execution_code="EXEC",
        beam_code="BEAM",
        process_code="PROCESS",
        result_code=BeamProcessResult.FAILED,
        started_at=local_time,
        finished_at=local_time,
        actor_name=" 操作人 ",
    )
    assert data.started_at == BASE_TIME - timedelta(hours=8)
    assert data.actor_name == "操作人"
    with pytest.raises(ValidationError):
        BeamProcessExecutionCreate(
            execution_code="EXEC",
            beam_code="BEAM",
            process_code="PROCESS",
            result_code=BeamProcessResult.SUCCESS,
            started_at=BASE_TIME,
            finished_at=BASE_TIME - timedelta(seconds=1),
            actor_name="操作人",
        )
    with pytest.raises(ValidationError):
        BeamProcessExecutionVoid(void_reason="原因")


def test_v6_records_all_results_repeats_and_uses_business_codes():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, global_process_code = _setup(suffix)
    try:
        records = []
        for index, result in enumerate(BeamProcessResult):
            records.append(services.process_records.record(_create_data(
                suffix,
                project_code,
                beam_code,
                process_code if index != 1 else global_process_code,
                execution_code=f"V6_EXEC_{index}_{suffix}",
                result_code=result,
                started_at=BASE_TIME + timedelta(hours=index),
                finished_at=BASE_TIME + timedelta(hours=index, minutes=10),
            )))
        assert [item.result_code for item in records] == list(BeamProcessResult)
        assert all(item.project_code == project_code for item in records)
        assert all(item.beam_code == beam_code for item in records)
        assert records[1].process_code == global_process_code
        assert services.process_records.get(
            records[0].execution_code, project_code=project_code
        ) == records[0]
    finally:
        _cleanup(suffix)


def test_v6_project_scope_and_process_activity_are_enforced():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    other_project = f"V6_OTHER_{suffix}"
    try:
        services.projects.create(ProjectCreate(
            project_code=other_project, project_name="其他项目"
        ))
        with pytest.raises(BeamNotFoundError):
            services.process_records.record(_create_data(
                suffix, other_project, beam_code, process_code
            ))
        historical = services.process_records.record(_create_data(
            suffix, project_code, beam_code, process_code
        ))
        process = services.processes.get_by_code(
            process_code, project_code=project_code
        )
        services.processes.set_active(
            process.id, is_active=False, project_code=project_code
        )
        with pytest.raises(InactiveResourceError):
            services.process_records.record(_create_data(
                suffix,
                project_code,
                beam_code,
                process_code,
                execution_code=f"V6_INACTIVE_{suffix}",
            ))
        assert services.process_records.get(
            historical.execution_code, project_code=project_code
        ).id == historical.id
    finally:
        _cleanup(suffix)


def test_v6_idempotent_retry_survives_process_deactivation():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    code_only = _create_data(
        suffix,
        project_code,
        beam_code,
        process_code,
        execution_code=f"V6_CODE_ONLY_{suffix}",
    )
    external = _create_data(
        suffix,
        project_code,
        beam_code,
        process_code,
        execution_code=f"V6_EXTERNAL_{suffix}",
        source=RecordSource.IMPORT,
        external_record_id=f"V6_EXT_{suffix}",
    )
    try:
        code_record = services.process_records.record(code_only)
        external_record = services.process_records.record(external)
        process = services.processes.get_by_code(
            process_code, project_code=project_code
        )
        services.processes.set_active(
            process.id, is_active=False, project_code=project_code
        )

        assert services.process_records.record(code_only) == code_record
        assert services.process_records.record(external) == external_record
        assert services.process_records._recover_concurrent_record(
            external
        ) == external_record
        with pytest.raises(ResourceConflictError):
            services.process_records.record(external.model_copy(update={
                "result_code": BeamProcessResult.FAILED,
            }))
        with pytest.raises(InactiveResourceError):
            services.process_records.record(code_only.model_copy(update={
                "execution_code": f"V6_NEW_INACTIVE_PROCESS_{suffix}",
            }))
    finally:
        _cleanup(suffix)


def test_v6_idempotent_retry_survives_project_deactivation():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    data = _create_data(
        suffix,
        project_code,
        beam_code,
        process_code,
        source=RecordSource.SYSTEM,
        external_record_id=f"V6_PROJECT_EXT_{suffix}",
    )
    try:
        record = services.process_records.record(data)
        project = services.projects.get_by_code(project_code)
        services.projects.set_active(project.id, is_active=False)

        assert services.process_records.record(data) == record
        assert services.process_records._recover_concurrent_record(data) == record
        with pytest.raises(InactiveResourceError):
            services.process_records.record(data.model_copy(update={
                "execution_code": f"V6_NEW_INACTIVE_PROJECT_{suffix}",
                "external_record_id": f"V6_NEW_PROJECT_EXT_{suffix}",
            }))
    finally:
        _cleanup(suffix)


def test_v6_idempotency_returns_same_record_and_rejects_changed_content():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    try:
        data = _create_data(
            suffix,
            project_code,
            beam_code,
            process_code,
            source=RecordSource.IMPORT,
            external_record_id=f"EXT_{suffix}",
        )
        first = services.process_records.record(data)
        assert services.process_records.record(data) == first
        with pytest.raises(ResourceConflictError):
            services.process_records.record(data.model_copy(update={
                "execution_code": f"V6_OTHER_EXEC_{suffix}",
                "result_code": BeamProcessResult.FAILED,
            }))
        with SessionLocal() as session:
            assert session.query(BeamProcessExecution).filter_by(
                external_record_id=f"EXT_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)


def test_v6_void_is_idempotent_and_correction_is_traceable():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    username = f"v6_user_{suffix}"
    try:
        user = services.users.create(UserCreate(
            username=username,
            display_name="V6作废人",
            password_hash=_hash(suffix),
        ))
        original = services.process_records.record(_create_data(
            suffix, project_code, beam_code, process_code
        ))
        void_data = BeamProcessExecutionVoid(
            voided_by_user_id=user.id, void_reason="录入时间错误"
        )
        voided = services.process_records.void(
            original.execution_code, void_data, project_code=project_code
        )
        repeated = services.process_records.void(
            original.execution_code,
            BeamProcessExecutionVoid(
                voided_by_name="另一个人", void_reason="不能覆盖首次原因"
            ),
            project_code=project_code,
        )
        assert voided.is_voided is True
        assert voided.voided_by_name == "V6作废人"
        assert repeated.void_reason == "录入时间错误"
        assert repeated.voided_at == voided.voided_at
        assert services.process_records.record(_create_data(
            suffix, project_code, beam_code, process_code
        )).is_voided is True

        correction = services.process_records.record(_create_data(
            suffix,
            project_code,
            beam_code,
            process_code,
            execution_code=f"V6_CORRECTION_{suffix}",
            supersedes_execution_code=original.execution_code,
            finished_at=BASE_TIME + timedelta(minutes=40),
        ))
        assert correction.supersedes_execution_code == original.execution_code
        with pytest.raises(ResourceConflictError):
            services.process_records.record(_create_data(
                suffix,
                project_code,
                beam_code,
                process_code,
                execution_code=f"V6_SECOND_CORRECTION_{suffix}",
                supersedes_execution_code=original.execution_code,
            ))
    finally:
        _cleanup(suffix)


def test_v6_filters_pages_stably_and_has_no_beam_side_effects():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    try:
        before_beam = services.beams.get_by_code(beam_code, project_code=project_code)
        with SessionLocal() as session:
            beam_id = session.query(Beam.id).filter_by(beam_code=beam_code).scalar()
            before_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        created = [
            services.process_records.record(_create_data(
                suffix,
                project_code,
                beam_code,
                process_code,
                execution_code=f"V6_PAGE_{index}_{suffix}",
                result_code=(
                    BeamProcessResult.SUCCESS
                    if index != 1
                    else BeamProcessResult.FAILED
                ),
                finished_at=BASE_TIME + timedelta(hours=index),
            ))
            for index in range(3)
        ]
        page = services.process_records.list(
            BeamProcessExecutionFilter(
                project_code=project_code,
                result_codes=[BeamProcessResult.SUCCESS],
                keyword=suffix,
            ),
            PageRequest(page_size=1, include_total=False),
            sort_by=BeamProcessExecutionSortField.FINISHED_AT,
            sort_order=SortOrder.DESC,
        )
        assert [item.id for item in page.items] == [created[2].id]
        assert page.total is None
        assert page.has_next is True
        after_beam = services.beams.get_by_code(beam_code, project_code=project_code)
        with SessionLocal() as session:
            after_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        assert after_beam.status == before_beam.status
        assert after_events == before_events
        with pytest.raises(BeamProcessExecutionNotFoundError):
            services.process_records.get(created[0].execution_code)
    finally:
        _cleanup(suffix)


def test_v6_public_service_has_no_update_or_delete():
    service = create_database_services().process_records
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
    assert not hasattr(service, "start")
    assert not hasattr(service, "complete")


def test_v6_concurrent_idempotent_records_create_one_row():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    data = _create_data(
        suffix,
        project_code,
        beam_code,
        process_code,
        source=RecordSource.SYSTEM,
        external_record_id=f"CONCURRENT_{suffix}",
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: services.process_records.record(data), range(2)
            ))
        assert results[0].id == results[1].id
        with SessionLocal() as session:
            assert session.query(BeamProcessExecution).filter_by(
                external_record_id=f"CONCURRENT_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)


def test_v6_referenced_process_project_is_immutable():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, global_process_code = _setup(
        suffix
    )
    other_project = f"V6_OTHER_{suffix}"
    try:
        services.projects.create(ProjectCreate(
            project_code=other_project, project_name="其他项目"
        ))
        process = services.processes.get_by_code(
            process_code, project_code=project_code
        )
        data = _create_data(suffix, project_code, beam_code, process_code)
        record = services.process_records.record(data)

        with pytest.raises(ResourceConflictError):
            services.processes.update(
                process.id,
                ProcessDefinitionUpdate(project_code=other_project),
                project_code=project_code,
            )
        with pytest.raises(ResourceConflictError):
            services.processes.update(
                process.id,
                ProcessDefinitionUpdate(project_code=None),
                project_code=project_code,
            )

        updated = services.processes.update(
            process.id,
            ProcessDefinitionUpdate(
                project_code=project_code,
                process_name="更新后的项目工序",
            ),
            project_code=project_code,
        )
        assert updated.project_code == project_code
        assert updated.process_name == "更新后的项目工序"
        assert services.process_records.record(data) == record

        global_record = services.process_records.record(_create_data(
            suffix,
            project_code,
            beam_code,
            global_process_code,
            execution_code=f"V6_GLOBAL_EXEC_{suffix}",
        ))
        global_process = services.processes.get_by_code(global_process_code)
        with pytest.raises(ResourceConflictError):
            services.processes.update(
                global_process.id,
                ProcessDefinitionUpdate(project_code=other_project),
            )
        assert services.process_records.get(
            global_record.execution_code,
            project_code=project_code,
        ) == global_record
    finally:
        _cleanup(suffix)


def test_v6_unreferenced_process_can_change_project():
    suffix = uuid4().hex[:8]
    services, project_code, _, process_code, _ = _setup(suffix)
    other_project = f"V6_OTHER_{suffix}"
    try:
        services.projects.create(ProjectCreate(
            project_code=other_project, project_name="其他项目"
        ))
        process = services.processes.get_by_code(
            process_code, project_code=project_code
        )
        updated = services.processes.update(
            process.id,
            ProcessDefinitionUpdate(project_code=other_project),
            project_code=project_code,
        )
        assert updated.project_code == other_project
    finally:
        _cleanup(suffix)


def test_v6_record_and_process_project_change_cannot_break_scope():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    other_project = f"V6_OTHER_{suffix}"
    data = _create_data(suffix, project_code, beam_code, process_code)
    try:
        services.projects.create(ProjectCreate(
            project_code=other_project, project_name="其他项目"
        ))
        process = services.processes.get_by_code(
            process_code, project_code=project_code
        )

        def record_execution():
            return services.process_records.record(data)

        def move_process():
            return services.processes.update(
                process.id,
                ProcessDefinitionUpdate(project_code=other_project),
                project_code=project_code,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(record_execution),
                executor.submit(move_process),
            ]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(future.result())
                except (ProcessDefinitionNotFoundError, ResourceConflictError) as error:
                    outcomes.append(error)

        with SessionLocal() as session:
            execution = session.query(BeamProcessExecution).filter_by(
                execution_code=data.execution_code
            ).one_or_none()
            stored_process = session.query(ProcessDefinition).filter_by(
                id=process.id
            ).one()
            assert execution is None or stored_process.project_id in {
                None,
                execution.project_id,
            }
        assert sum(isinstance(item, Exception) for item in outcomes) == 1
    finally:
        _cleanup(suffix)


def test_v6_global_beam_only_accepts_global_process():
    suffix = uuid4().hex[:8]
    services, project_code, _, project_process_code, global_process_code = _setup(suffix)
    global_type_code = f"V6_GLOBAL_TYPE_{suffix}"
    global_beam_code = f"V6_GLOBAL_BEAM_{suffix}"
    try:
        services.beam_types.create(BeamTypeCreate(
            type_code=global_type_code, type_name="全局梁型"
        ))
        services.beams.create(BeamCreate(
            beam_code=global_beam_code, beam_type_code=global_type_code
        ))
        with pytest.raises(ProcessDefinitionNotFoundError):
            services.process_records.record(_create_data(
                suffix,
                None,
                global_beam_code,
                project_process_code,
                execution_code=f"V6_INVALID_GLOBAL_{suffix}",
            ))
        record = services.process_records.record(_create_data(
            suffix,
            None,
            global_beam_code,
            global_process_code,
            execution_code=f"V6_VALID_GLOBAL_{suffix}",
        ))
        assert record.project_code is None
        assert record.process_code == global_process_code
        with pytest.raises(BeamProcessExecutionNotFoundError):
            services.process_records.get(
                record.execution_code, project_code=project_code
            )
    finally:
        _cleanup(suffix)


def test_v6_record_rolls_back_if_dto_conversion_fails(monkeypatch):
    from backend_db.services import beam_process_execution as service_module

    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)

    def fail_after_flush(*_args):
        raise RuntimeError("forced failure after flush")

    try:
        monkeypatch.setattr(service_module, "_to_read", fail_after_flush)
        with pytest.raises(RuntimeError, match="forced failure"):
            services.process_records.record(_create_data(
                suffix, project_code, beam_code, process_code
            ))
        with SessionLocal() as session:
            assert session.query(BeamProcessExecution).filter_by(
                execution_code=f"V6_EXEC_{suffix}"
            ).count() == 0
    finally:
        _cleanup(suffix)


def test_v6_concurrent_void_preserves_first_result():
    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    try:
        record = services.process_records.record(_create_data(
            suffix, project_code, beam_code, process_code
        ))

        def void_with(index: int):
            return services.process_records.void(
                record.execution_code,
                BeamProcessExecutionVoid(
                    voided_by_name=f"作废人{index}",
                    void_reason=f"原因{index}",
                ),
                project_code=project_code,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(void_with, range(2)))
        assert results[0].voided_at == results[1].voided_at
        assert results[0].void_reason == results[1].void_reason
        assert results[0].voided_by_name == results[1].voided_by_name
    finally:
        _cleanup(suffix)


def test_v6_conflict_recovery_returns_record_if_process_becomes_inactive(
    monkeypatch,
):
    from backend_db.services import beam_process_execution as service_module

    suffix = uuid4().hex[:8]
    services, project_code, beam_code, process_code, _ = _setup(suffix)
    data = _create_data(
        suffix,
        project_code,
        beam_code,
        process_code,
        source=RecordSource.DEVICE,
        external_record_id=f"V6_RECOVERY_{suffix}",
    )
    original_create = service_module.create_beam_process_execution
    original_get_process = service_module.get_process_definition_by_code

    def get_process_without_lock(session, code, *, for_update=False):
        return original_get_process(session, code, for_update=False)

    def simulate_concurrent_commit(_session, **values):
        with SessionLocal.begin() as other_session:
            original_create(other_session, **values)
            process = other_session.query(ProcessDefinition).filter_by(
                process_code=process_code
            ).one()
            process.is_active = False
        raise IntegrityError("INSERT", values, RuntimeError("duplicate"))

    try:
        monkeypatch.setattr(
            service_module,
            "create_beam_process_execution",
            simulate_concurrent_commit,
        )
        monkeypatch.setattr(
            service_module,
            "get_process_definition_by_code",
            get_process_without_lock,
        )
        record = services.process_records.record(data)
        assert record.execution_code == data.execution_code
        assert record.external_record_id == data.external_record_id
        with SessionLocal() as session:
            assert session.query(BeamProcessExecution).filter_by(
                external_record_id=f"V6_RECOVERY_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)
