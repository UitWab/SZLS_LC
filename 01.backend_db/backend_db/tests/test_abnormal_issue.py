from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import (
    AbnormalIssueNotFoundError,
    BeamNotFoundError,
    InactiveResourceError,
    ResourceConflictError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    AbnormalIssue,
    AppUser,
    Beam,
    BeamLifecycleEvent,
    BeamType,
    OperationAuditLog,
    Project,
    UserCredential,
)
from backend_db.schemas import (
    AbnormalIssueActorAction,
    AbnormalIssueCategory,
    AbnormalIssueClose,
    AbnormalIssueCreate,
    AbnormalIssueFilter,
    AbnormalIssueResolve,
    AbnormalIssueSeverity,
    AbnormalIssueSortField,
    AbnormalIssueStatus,
    BeamCreate,
    BeamTypeCreate,
    PageRequest,
    ProjectCreate,
    RecordSource,
    SortOrder,
    UserCreate,
    UserUpdate,
)


BASE_TIME = datetime(2026, 9, 22, 8, 0, 0)


def _setup(suffix: str):
    services = create_database_services()
    project_code = f"V9_PROJECT_{suffix}"
    other_project_code = f"V9_OTHER_PROJECT_{suffix}"
    type_code = f"V9_TYPE_{suffix}"
    beam_code = f"V9_BEAM_{suffix}"
    services.projects.create(ProjectCreate(
        project_code=project_code, project_name="V9测试项目"
    ))
    services.projects.create(ProjectCreate(
        project_code=other_project_code, project_name="V9其他项目"
    ))
    services.beam_types.create(BeamTypeCreate(
        type_code=type_code,
        type_name="V9测试梁型",
        project_code=project_code,
    ))
    services.beams.create(BeamCreate(
        beam_code=beam_code,
        beam_type_code=type_code,
        project_code=project_code,
    ))
    return services, project_code, other_project_code, beam_code


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        session.execute(delete(AbnormalIssue).where(
            AbnormalIssue.issue_code.contains(suffix)
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
        users = session.query(AppUser).filter(AppUser.username.contains(suffix)).all()
        user_ids = [item.id for item in users]
        if user_ids:
            session.execute(delete(UserCredential).where(
                UserCredential.user_id.in_(user_ids)
            ))
            session.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))


def _issue_data(suffix: str, project_code: str, beam_code: str | None, **changes):
    values = {
        "issue_code": f"V9_ISSUE_{suffix}",
        "project_code": project_code,
        "beam_code": beam_code,
        "category_code": AbnormalIssueCategory.QUALITY,
        "issue_type_code": "QUALITY_RECHECK_OVERDUE",
        "severity": AbnormalIssueSeverity.WARNING,
        "title": "质量复检超期",
        "message": "梁片质量复检超过计划时间",
        "occurred_at": BASE_TIME,
        "reported_by_name": "系统记录员",
        "source": RecordSource.SYSTEM,
        "external_record_id": f"V9_EXTERNAL_{suffix}",
    }
    values.update(changes)
    return AbnormalIssueCreate(**values)


def test_v9_schema_normalizes_time_and_validates_actions_and_range():
    local_time = BASE_TIME.replace(tzinfo=timezone(timedelta(hours=8)))
    data = AbnormalIssueCreate(
        issue_code="ISSUE",
        project_code="PROJECT",
        category_code=AbnormalIssueCategory.SAFETY,
        issue_type_code="LIFTING_RISK",
        severity=AbnormalIssueSeverity.CRITICAL,
        title=" 吊装风险 ",
        message=" 高风险作业状态异常 ",
        occurred_at=local_time,
    )
    assert data.occurred_at == BASE_TIME - timedelta(hours=8)
    assert data.title == "吊装风险"
    assert data.message == "高风险作业状态异常"
    with pytest.raises(ValidationError):
        AbnormalIssueActorAction()
    with pytest.raises(ValidationError):
        AbnormalIssueResolve(actor_name="处理人", resolution_summary=" ")
    with pytest.raises(ValidationError):
        AbnormalIssueFilter(
            project_code="PROJECT",
            occurred_at_from=BASE_TIME,
            occurred_at_to=BASE_TIME - timedelta(seconds=1),
        )


def test_v9_records_all_categories_without_beam_side_effects():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        before_beam = services.beams.get_by_code(beam, project_code=project)
        with SessionLocal() as session:
            beam_id = session.query(Beam.id).filter_by(beam_code=beam).scalar()
            before_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        records = []
        for index, category in enumerate(AbnormalIssueCategory):
            records.append(services.abnormal_issues.record(_issue_data(
                suffix,
                project,
                beam if index % 2 == 0 else None,
                issue_code=f"V9_{category.value}_{suffix}",
                category_code=category,
                issue_type_code=f"{category.value}_TEST",
                device_code=(f"DEVICE_{suffix}" if category == AbnormalIssueCategory.EQUIPMENT else None),
                external_record_id=f"V9_{category.value}_EXT_{suffix}",
            )))
        assert {item.category_code for item in records} == set(AbnormalIssueCategory)
        assert all(item.status == AbnormalIssueStatus.OPEN for item in records)
        after_beam = services.beams.get_by_code(beam, project_code=project)
        with SessionLocal() as session:
            after_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
        assert after_beam.status == before_beam.status
        assert after_events == before_events
    finally:
        _cleanup(suffix)


def test_v9_project_isolation_and_optional_beam_scope():
    suffix = uuid4().hex[:8]
    services, project, other_project, beam = _setup(suffix)
    try:
        record = services.abnormal_issues.record(_issue_data(suffix, project, beam))
        assert services.abnormal_issues.get(
            record.issue_code, project_code=project
        ) == record
        with pytest.raises(AbnormalIssueNotFoundError):
            services.abnormal_issues.get(
                record.issue_code, project_code=other_project
            )
        with pytest.raises(BeamNotFoundError):
            services.abnormal_issues.record(_issue_data(
                suffix,
                other_project,
                beam,
                issue_code=f"V9_WRONG_SCOPE_{suffix}",
                external_record_id=f"V9_WRONG_SCOPE_EXT_{suffix}",
            ))
    finally:
        _cleanup(suffix)


def test_v9_external_idempotency_concurrency_and_inactive_retry():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    data = _issue_data(suffix, project, beam)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: services.abnormal_issues.record(data), range(2)
            ))
        assert results[0].id == results[1].id
        project_item = services.projects.get_by_code(project)
        services.projects.set_active(project_item.id, is_active=False)
        assert services.abnormal_issues.record(data).id == results[0].id
        with pytest.raises(InactiveResourceError):
            services.abnormal_issues.record(data.model_copy(update={
                "issue_code": f"V9_NEW_INACTIVE_{suffix}",
                "external_record_id": f"V9_NEW_INACTIVE_EXT_{suffix}",
            }))
        with pytest.raises(ResourceConflictError):
            services.abnormal_issues.record(data.model_copy(update={
                "issue_code": f"V9_CHANGED_{suffix}",
                "message": "不同的异常内容",
            }))
        with SessionLocal() as session:
            assert session.query(AbnormalIssue).filter_by(
                external_record_id=f"V9_EXTERNAL_{suffix}"
            ).count() == 1
    finally:
        _cleanup(suffix)


def test_v9_new_record_waits_for_project_deactivation(monkeypatch):
    from backend_db.services import _project_scope as project_scope_module

    suffix = uuid4().hex[:8]
    services, project_code, _, beam = _setup(suffix)
    data = _issue_data(
        suffix,
        project_code,
        beam,
        issue_code=f"V9_DEACTIVATE_RACE_{suffix}",
        external_record_id=f"V9_DEACTIVATE_RACE_EXT_{suffix}",
    )
    project_lookup_started = Event()
    original_get_project_by_code = project_scope_module.get_project_by_code

    def observed_get_project_by_code(*args, **kwargs):
        project_lookup_started.set()
        return original_get_project_by_code(*args, **kwargs)

    monkeypatch.setattr(
        project_scope_module,
        "get_project_by_code",
        observed_get_project_by_code,
    )
    session = SessionLocal()
    transaction = session.begin()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        project = session.scalar(
            select(Project)
            .where(Project.project_code == project_code)
            .with_for_update()
        )
        project.is_active = False
        session.flush()

        future = executor.submit(services.abnormal_issues.record, data)
        assert project_lookup_started.wait(timeout=2)
        with pytest.raises(FutureTimeoutError):
            future.result(timeout=0.2)

        transaction.commit()
        with pytest.raises(InactiveResourceError):
            future.result(timeout=5)
        with SessionLocal() as verify_session:
            assert verify_session.query(AbnormalIssue).filter_by(
                issue_code=data.issue_code
            ).count() == 0
    finally:
        if transaction.is_active:
            transaction.rollback()
        session.close()
        executor.shutdown(wait=True)
        _cleanup(suffix)


def test_v9_split_idempotency_keys_are_rejected():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        first = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            beam,
            issue_code=f"V9_SPLIT_A_{suffix}",
            external_record_id=f"V9_SPLIT_EXT_A_{suffix}",
        ))
        second = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            beam,
            issue_code=f"V9_SPLIT_B_{suffix}",
            external_record_id=f"V9_SPLIT_EXT_B_{suffix}",
        ))
        assert first.id != second.id
        with pytest.raises(ResourceConflictError, match="指向不同记录"):
            services.abnormal_issues.record(_issue_data(
                suffix,
                project,
                beam,
                issue_code=first.issue_code,
                external_record_id=f"V9_SPLIT_EXT_B_{suffix}",
            ))
    finally:
        _cleanup(suffix)


def test_v9_user_names_are_immutable_snapshots_across_actions():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    username = f"v9_snapshot_{suffix}"
    try:
        user = services.users.create(UserCreate(
            username=username,
            display_name="上报时名称",
            password_hash=f"v9-test-password-hash-{suffix}",
        ))
        item = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            beam,
            reported_by_user_id=user.id,
            reported_by_name=None,
        ))
        assert item.reported_by_name == "上报时名称"

        services.users.update(user.id, UserUpdate(display_name="处理时名称"))
        item = services.abnormal_issues.start_processing(
            item.issue_code,
            AbnormalIssueActorAction(actor_user_id=user.id),
            project_code=project,
        )
        assert item.reported_by_name == "上报时名称"
        assert item.processing_by_name == "处理时名称"

        services.users.update(user.id, UserUpdate(display_name="解决时名称"))
        item = services.abnormal_issues.resolve(
            item.issue_code,
            AbnormalIssueResolve(
                actor_user_id=user.id,
                resolution_summary="完成整改",
            ),
            project_code=project,
        )
        assert item.processing_by_name == "处理时名称"
        assert item.resolved_by_name == "解决时名称"

        services.users.update(user.id, UserUpdate(display_name="关闭时名称"))
        item = services.abnormal_issues.close(
            item.issue_code,
            AbnormalIssueClose(actor_user_id=user.id),
            project_code=project,
        )
        assert item.resolved_by_name == "解决时名称"
        assert item.closed_by_name == "关闭时名称"

        services.users.update(user.id, UserUpdate(display_name="后续名称"))
        stored = services.abnormal_issues.get(
            item.issue_code, project_code=project
        )
        assert stored.reported_by_name == "上报时名称"
        assert stored.processing_by_name == "处理时名称"
        assert stored.resolved_by_name == "解决时名称"
        assert stored.closed_by_name == "关闭时名称"
    finally:
        _cleanup(suffix)


def test_v9_concurrent_start_processing_preserves_first_snapshot_for_20_rounds():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)

    def start(issue_code: str, actor_name: str):
        try:
            item = services.abnormal_issues.start_processing(
                issue_code,
                AbnormalIssueActorAction(actor_name=actor_name),
                project_code=project,
            )
            return "ok", item.processing_by_name
        except ResourceConflictError:
            return "conflict", actor_name

    try:
        for round_index in range(20):
            item = services.abnormal_issues.record(_issue_data(
                suffix,
                project,
                beam,
                issue_code=f"V9_STATE_R{round_index}_{suffix}",
                external_record_id=f"V9_STATE_EXT_R{round_index}_{suffix}",
            ))
            actors = (f"处理人A{round_index}", f"处理人B{round_index}")
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(
                    lambda actor: start(item.issue_code, actor), actors
                ))
            assert sorted(result[0] for result in results) == ["conflict", "ok"]
            stored = services.abnormal_issues.get(
                item.issue_code, project_code=project
            )
            assert stored.status == AbnormalIssueStatus.IN_PROGRESS
            assert stored.processing_by_name in actors
    finally:
        _cleanup(suffix)


def test_v9_state_flow_direct_resolve_and_idempotent_actions():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        item = services.abnormal_issues.record(_issue_data(suffix, project, beam))
        start = AbnormalIssueActorAction(actor_name="处理人")
        started = services.abnormal_issues.start_processing(
            item.issue_code, start, project_code=project
        )
        assert started.status == AbnormalIssueStatus.IN_PROGRESS
        assert services.abnormal_issues.start_processing(
            item.issue_code, start, project_code=project
        ).processing_started_at == started.processing_started_at
        with pytest.raises(ResourceConflictError):
            services.abnormal_issues.start_processing(
                item.issue_code,
                AbnormalIssueActorAction(actor_name="其他处理人"),
                project_code=project,
            )

        resolve = AbnormalIssueResolve(
            actor_name="解决人", resolution_summary="已完成整改"
        )
        resolved = services.abnormal_issues.resolve(
            item.issue_code, resolve, project_code=project
        )
        assert resolved.status == AbnormalIssueStatus.RESOLVED
        assert services.abnormal_issues.resolve(
            item.issue_code, resolve, project_code=project
        ).resolved_at == resolved.resolved_at
        with pytest.raises(ResourceConflictError):
            services.abnormal_issues.resolve(
                item.issue_code,
                resolve.model_copy(update={"resolution_summary": "不同结论"}),
                project_code=project,
            )

        close = AbnormalIssueClose(actor_name="复核人", close_note="复核通过")
        closed = services.abnormal_issues.close(
            item.issue_code, close, project_code=project
        )
        assert closed.status == AbnormalIssueStatus.CLOSED
        assert services.abnormal_issues.close(
            item.issue_code, close, project_code=project
        ).closed_at == closed.closed_at

        direct = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            None,
            issue_code=f"V9_DIRECT_{suffix}",
            external_record_id=f"V9_DIRECT_EXT_{suffix}",
        ))
        direct_resolved = services.abnormal_issues.resolve(
            direct.issue_code, resolve, project_code=project
        )
        assert direct_resolved.status == AbnormalIssueStatus.RESOLVED
        assert direct_resolved.processing_started_at is None
    finally:
        _cleanup(suffix)


def test_v9_rejects_close_before_resolve_and_transition_after_close():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        item = services.abnormal_issues.record(_issue_data(suffix, project, beam))
        close = AbnormalIssueClose(actor_name="复核人")
        with pytest.raises(ResourceConflictError):
            services.abnormal_issues.close(
                item.issue_code, close, project_code=project
            )
        services.abnormal_issues.resolve(
            item.issue_code,
            AbnormalIssueResolve(
                actor_name="解决人", resolution_summary="问题已解决"
            ),
            project_code=project,
        )
        services.abnormal_issues.close(
            item.issue_code, close, project_code=project
        )
        with pytest.raises(ResourceConflictError):
            services.abnormal_issues.start_processing(
                item.issue_code,
                AbnormalIssueActorAction(actor_name="迟到处理人"),
                project_code=project,
            )
    finally:
        _cleanup(suffix)


def test_v9_state_action_failures_roll_back_each_transition(monkeypatch):
    from backend_db.services import abnormal_issue as service_module

    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    original_to_read = service_module._to_read

    def fail_after_flush(*_args):
        raise RuntimeError("forced state conversion failure")

    try:
        start_item = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            beam,
            issue_code=f"V9_ROLLBACK_START_{suffix}",
            external_record_id=f"V9_ROLLBACK_START_EXT_{suffix}",
        ))
        with monkeypatch.context() as context:
            context.setattr(service_module, "_to_read", fail_after_flush)
            with pytest.raises(RuntimeError, match="forced state conversion failure"):
                services.abnormal_issues.start_processing(
                    start_item.issue_code,
                    AbnormalIssueActorAction(actor_name="处理人"),
                    project_code=project,
                )
        assert services.abnormal_issues.get(
            start_item.issue_code, project_code=project
        ).status == AbnormalIssueStatus.OPEN

        resolve_item = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            beam,
            issue_code=f"V9_ROLLBACK_RESOLVE_{suffix}",
            external_record_id=f"V9_ROLLBACK_RESOLVE_EXT_{suffix}",
        ))
        resolve_item = services.abnormal_issues.start_processing(
            resolve_item.issue_code,
            AbnormalIssueActorAction(actor_name="处理人"),
            project_code=project,
        )
        with monkeypatch.context() as context:
            context.setattr(service_module, "_to_read", fail_after_flush)
            with pytest.raises(RuntimeError, match="forced state conversion failure"):
                services.abnormal_issues.resolve(
                    resolve_item.issue_code,
                    AbnormalIssueResolve(
                        actor_name="解决人", resolution_summary="已解决"
                    ),
                    project_code=project,
                )
        stored = services.abnormal_issues.get(
            resolve_item.issue_code, project_code=project
        )
        assert stored.status == AbnormalIssueStatus.IN_PROGRESS
        assert stored.resolved_at is None

        close_item = services.abnormal_issues.resolve(
            resolve_item.issue_code,
            AbnormalIssueResolve(
                actor_name="解决人", resolution_summary="已解决"
            ),
            project_code=project,
        )
        with monkeypatch.context() as context:
            context.setattr(service_module, "_to_read", fail_after_flush)
            with pytest.raises(RuntimeError, match="forced state conversion failure"):
                services.abnormal_issues.close(
                    close_item.issue_code,
                    AbnormalIssueClose(actor_name="复核人"),
                    project_code=project,
                )
        stored = services.abnormal_issues.get(
            close_item.issue_code, project_code=project
        )
        assert stored.status == AbnormalIssueStatus.RESOLVED
        assert stored.closed_at is None
        assert service_module._to_read is original_to_read
    finally:
        _cleanup(suffix)


def test_v9_actions_do_not_write_lifecycle_or_audit_side_effects():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        with SessionLocal() as session:
            beam_id = session.query(Beam.id).filter_by(beam_code=beam).scalar()
            before_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
            before_audits = session.query(OperationAuditLog).filter(
                OperationAuditLog.resource_code.contains(suffix)
            ).count()
        item = services.abnormal_issues.record(_issue_data(suffix, project, beam))
        services.abnormal_issues.start_processing(
            item.issue_code,
            AbnormalIssueActorAction(actor_name="处理人"),
            project_code=project,
        )
        services.abnormal_issues.resolve(
            item.issue_code,
            AbnormalIssueResolve(actor_name="解决人", resolution_summary="已解决"),
            project_code=project,
        )
        services.abnormal_issues.close(
            item.issue_code,
            AbnormalIssueClose(actor_name="关闭人"),
            project_code=project,
        )
        with SessionLocal() as session:
            after_events = session.query(BeamLifecycleEvent).filter_by(
                beam_id=beam_id
            ).count()
            after_audits = session.query(OperationAuditLog).filter(
                OperationAuditLog.resource_code.contains(suffix)
            ).count()
        assert after_events == before_events
        assert after_audits == before_audits
    finally:
        _cleanup(suffix)


def test_v9_filters_and_pages_are_stable():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        created = [
            services.abnormal_issues.record(_issue_data(
                suffix,
                project,
                beam if index != 1 else None,
                issue_code=f"V9_PAGE_{index}_{suffix}",
                category_code=(
                    AbnormalIssueCategory.QUALITY
                    if index != 1
                    else AbnormalIssueCategory.LOGISTICS
                ),
                severity=(
                    AbnormalIssueSeverity.CRITICAL
                    if index != 1
                    else AbnormalIssueSeverity.INFO
                ),
                device_code=f"DEVICE_{suffix}",
                occurred_at=BASE_TIME,
                external_record_id=f"V9_PAGE_EXT_{index}_{suffix}",
            ))
            for index in range(3)
        ]
        page = services.abnormal_issues.list(
            AbnormalIssueFilter(
                project_code=project,
                beam_code=beam,
                device_code=f"DEVICE_{suffix}",
                category_codes=[AbnormalIssueCategory.QUALITY],
                severities=[AbnormalIssueSeverity.CRITICAL],
                statuses=[AbnormalIssueStatus.OPEN],
                keyword=suffix,
            ),
            PageRequest(page_size=1, include_total=False),
            sort_by=AbnormalIssueSortField.OCCURRED_AT,
            sort_order=SortOrder.ASC,
        )
        assert [item.id for item in page.items] == [created[0].id]
        assert page.total is None
        assert page.has_next is True
    finally:
        _cleanup(suffix)


def test_v9_empty_multivalue_filter_and_keyword_wildcards_are_literal():
    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)
    try:
        special = services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            None,
            issue_code=f"V9SPECIAL{suffix}",
            issue_type_code="SPECIAL%_TYPE",
            title="包含百分号%和下划线_",
            external_record_id=f"V9_SPECIAL_EXT_{suffix}",
        ))
        services.abnormal_issues.record(_issue_data(
            suffix,
            project,
            None,
            issue_code=f"V9PLAIN{suffix}",
            issue_type_code="PLAINTYPE",
            title="普通标题",
            external_record_id=f"V9_PLAIN_EXT_{suffix}",
        ))
        empty = services.abnormal_issues.list(AbnormalIssueFilter(
            project_code=project, statuses=[]
        ))
        assert empty.items == []
        assert empty.total == 0

        percent = services.abnormal_issues.list(AbnormalIssueFilter(
            project_code=project, keyword="%"
        ))
        underscore = services.abnormal_issues.list(AbnormalIssueFilter(
            project_code=project, keyword="_"
        ))
        assert [item.id for item in percent.items] == [special.id]
        assert [item.id for item in underscore.items] == [special.id]
    finally:
        _cleanup(suffix)


def test_v9_record_rolls_back_if_conversion_fails(monkeypatch):
    from backend_db.services import abnormal_issue as service_module

    suffix = uuid4().hex[:8]
    services, project, _, beam = _setup(suffix)

    def fail_after_flush(*_args):
        raise RuntimeError("forced failure after flush")

    try:
        monkeypatch.setattr(service_module, "_to_read", fail_after_flush)
        with pytest.raises(RuntimeError, match="forced failure"):
            services.abnormal_issues.record(_issue_data(suffix, project, beam))
        with SessionLocal() as session:
            assert session.query(AbnormalIssue).filter_by(
                issue_code=f"V9_ISSUE_{suffix}"
            ).count() == 0
    finally:
        _cleanup(suffix)


def test_v9_public_service_has_no_detection_notification_or_delete_methods():
    service = create_database_services().abnormal_issues
    for method in (
        "update",
        "delete",
        "reopen",
        "detect",
        "calculate",
        "notify",
        "dispatch",
        "control_device",
    ):
        assert not hasattr(service, method)
