from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from backend_db.crud.operation_audit_log import (
    create_operation_audit_log,
    get_operation_audit_log,
    list_operation_audit_logs,
)
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    InvalidDataError,
    OperationAuditLogNotFoundError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    AppUser,
    OperationAuditLog,
    Project,
    UserCredential,
)
from backend_db.schemas import (
    OperationAuditLogCreate,
    OperationAuditLogFilter,
    OperationAuditLogRead,
    OperationAuditLogScope,
    OperationAuditLogSortField,
    PageRequest,
    ProjectCreate,
    SortOrder,
    UserCreate,
)


def _hash(label: str) -> str:
    return f"$argon2id$v=19$m=65536,t=3,p=4${label}_hash_value"


def _cleanup(suffix: str) -> None:
    with SessionLocal.begin() as session:
        session.execute(delete(OperationAuditLog).where(
            OperationAuditLog.request_id.contains(suffix)
        ))
        users = session.query(AppUser).filter(
            AppUser.username.contains(suffix)
        ).all()
        user_ids = [user.id for user in users]
        if user_ids:
            session.execute(delete(UserCredential).where(
                UserCredential.user_id.in_(user_ids)
            ))
        for user in users:
            session.delete(user)
        session.execute(delete(Project).where(
            Project.project_code.contains(suffix)
        ))


def test_operation_audit_log_schema_rejects_sensitive_or_invalid_input():
    timestamp = datetime(2026, 9, 7, 8, 0, 0)
    data = OperationAuditLogCreate(
        actor_name="  系统管理员  ",
        action_code="  USER_UPDATED  ",
        resource_type="  USER  ",
        result_code="  SUCCESS  ",
        occurred_at=timestamp.replace(tzinfo=timezone(timedelta(hours=8))),
    )
    assert data.actor_name == "系统管理员"
    assert data.action_code == "USER_UPDATED"
    assert data.occurred_at == timestamp - timedelta(hours=8)
    assert data.occurred_at.tzinfo is None

    with pytest.raises(ValidationError):
        OperationAuditLogCreate(
            action_code="LOGIN_SUCCEEDED",
            resource_type="USER",
            result_code="SUCCESS",
            occurred_at=timestamp,
            password_hash="must-not-be-accepted",
        )
    with pytest.raises(ValidationError):
        OperationAuditLogCreate(
            action_code=" ",
            resource_type="USER",
            result_code="SUCCESS",
            occurred_at=timestamp,
        )
    with pytest.raises(ValidationError):
        OperationAuditLogFilter(
            scope=OperationAuditLogScope.SYSTEM,
            occurred_at_from=timestamp,
            occurred_at_to=timestamp - timedelta(seconds=1),
        )
    with pytest.raises(ValidationError):
        OperationAuditLogFilter(scope=OperationAuditLogScope.PROJECT)
    with pytest.raises(ValidationError):
        OperationAuditLogFilter(
            scope=OperationAuditLogScope.SYSTEM,
            project_code="PROJECT_NOT_ALLOWED",
        )


def test_operation_audit_log_crud_flushes_without_committing():
    suffix = uuid4().hex[:8]
    request_id = f"crud-{suffix}"
    timestamp = datetime(2026, 9, 7, 8, 0, 0)
    with UnitOfWork() as unit:
        audit_log = create_operation_audit_log(
            unit.session,
            project_id=None,
            actor_user_id=None,
            actor_name="SYSTEM",
            action_code="SYSTEM_CHECK",
            resource_type="SYSTEM",
            resource_code=None,
            result_code="SUCCESS",
            request_id=request_id,
            source="SYSTEM",
            summary=None,
            occurred_at=timestamp,
        )
        assert audit_log.id is not None
        assert get_operation_audit_log(unit.session, audit_log.id)[0] is audit_log
        items, total, has_next = list_operation_audit_logs(
            unit.session, request_id=request_id
        )
        assert [item[0].id for item in items] == [audit_log.id]
        assert total == 1
        assert has_next is False

    with SessionLocal() as session:
        assert session.query(OperationAuditLog).filter_by(
            request_id=request_id
        ).count() == 0


def test_operation_audit_log_service_records_filters_and_pages():
    suffix = uuid4().hex[:8]
    project_code = f"AUDIT_PROJECT_{suffix}"
    username = f"audit_user_{suffix}"
    request_ids = [f"audit-{suffix}-{number}" for number in range(3)]
    services = create_database_services()
    base_time = datetime(2026, 9, 7, 8, 0, 0)
    try:
        services.projects.create(ProjectCreate(
            project_code=project_code, project_name="审计测试项目"
        ))
        user = services.users.create(UserCreate(
            username=username,
            display_name="审计操作人",
            password_hash=_hash(suffix),
        ))

        first = services.audit_logs.record(OperationAuditLogCreate(
            project_code=project_code,
            actor_user_id=user.id,
            action_code="BEAM_UPDATED",
            resource_type="BEAM",
            resource_code=f"BEAM_{suffix}",
            result_code="SUCCESS",
            request_id=request_ids[0],
            source="WEB",
            summary="更新梁基础资料",
            occurred_at=base_time,
        ))
        assert isinstance(first, OperationAuditLogRead)
        assert first.project_code == project_code
        assert first.actor_name == "审计操作人"
        assert services.audit_logs.get(
            first.id,
            scope=OperationAuditLogScope.PROJECT,
            project_code=project_code,
        ) == first

        services.audit_logs.record(OperationAuditLogCreate(
            actor_name=f"unknown_{suffix}",
            action_code="LOGIN_FAILED",
            resource_type="USER",
            result_code="FAILURE",
            request_id=request_ids[1],
            source="WEB",
            occurred_at=base_time + timedelta(seconds=1),
        ))
        services.audit_logs.record(OperationAuditLogCreate(
            project_code=project_code,
            actor_user_id=user.id,
            actor_name="操作人快照",
            action_code="ROLE_ASSIGNED",
            resource_type="ROLE",
            resource_code=f"ROLE_{suffix}",
            result_code="SUCCESS",
            request_id=request_ids[2],
            source="WEB",
            occurred_at=base_time + timedelta(seconds=2),
        ))

        page_one = services.audit_logs.list(
            OperationAuditLogFilter(
                scope=OperationAuditLogScope.ALL, keyword=suffix
            ),
            PageRequest(page=1, page_size=2),
        )
        page_two = services.audit_logs.list(
            OperationAuditLogFilter(
                scope=OperationAuditLogScope.ALL, keyword=suffix
            ),
            PageRequest(page=2, page_size=2),
        )
        assert [item.action_code for item in page_one.items] == [
            "ROLE_ASSIGNED",
            "LOGIN_FAILED",
        ]
        assert page_one.total == 3
        assert page_one.has_next is True
        assert page_one.has_previous is False
        assert [item.action_code for item in page_two.items] == ["BEAM_UPDATED"]
        assert page_two.has_next is False
        assert page_two.has_previous is True

        project_logs = services.audit_logs.list(
            OperationAuditLogFilter(
                scope=OperationAuditLogScope.PROJECT,
                project_code=project_code,
                actor_user_id=user.id,
                result_code="SUCCESS",
                occurred_at_from=base_time,
                occurred_at_to=base_time + timedelta(seconds=2),
            ),
            PageRequest(page_size=10),
            sort_by=OperationAuditLogSortField.OCCURRED_AT,
            sort_order=SortOrder.ASC,
        )
        assert [item.action_code for item in project_logs.items] == [
            "BEAM_UPDATED",
            "ROLE_ASSIGNED",
        ]

        without_total = services.audit_logs.list(
            OperationAuditLogFilter(
                scope=OperationAuditLogScope.ALL, keyword=suffix
            ),
            PageRequest(page_size=2, include_total=False),
        )
        assert without_total.total is None
        assert without_total.has_next is True

        with pytest.raises(OperationAuditLogNotFoundError):
            services.audit_logs.get(
                9_000_000_000, scope=OperationAuditLogScope.ALL
            )
        with pytest.raises(ProjectNotFoundError):
            services.audit_logs.record(OperationAuditLogCreate(
                project_code=f"MISSING_{suffix}",
                action_code="TEST",
                resource_type="SYSTEM",
                result_code="FAILURE",
                request_id=f"missing-project-{suffix}",
                occurred_at=base_time,
            ))
        with pytest.raises(UserNotFoundError):
            services.audit_logs.record(OperationAuditLogCreate(
                actor_user_id=9_000_000_000,
                action_code="TEST",
                resource_type="SYSTEM",
                result_code="FAILURE",
                request_id=f"missing-user-{suffix}",
                occurred_at=base_time,
            ))
    finally:
        _cleanup(suffix)


@pytest.mark.parametrize(
    "query_args",
    [
        {"page": 0},
        {"page_size": 101},
        {"sort_by": "summary"},
        {"sort_order": "random"},
        {"project_id": 1, "all_projects": True},
    ],
)
def test_operation_audit_log_crud_rejects_unsafe_query_arguments(query_args):
    with UnitOfWork() as unit:
        with pytest.raises(ValueError):
            list_operation_audit_logs(unit.session, **query_args)


@pytest.mark.parametrize(
    ("field_name", "max_length"),
    [
        ("project_code", 64),
        ("actor_name", 128),
        ("action_code", 64),
        ("resource_type", 64),
        ("resource_code", 128),
        ("result_code", 32),
        ("request_id", 128),
        ("source", 32),
        ("summary", 500),
    ],
)
def test_operation_audit_log_create_enforces_string_boundaries(
    field_name, max_length
):
    values = {
        "action_code": "TEST",
        "resource_type": "SYSTEM",
        "result_code": "SUCCESS",
        "occurred_at": datetime(2026, 9, 7, 8, 0, 0),
    }
    values[field_name] = "X" * max_length
    assert len(getattr(OperationAuditLogCreate(**values), field_name)) == max_length

    values[field_name] = "X" * (max_length + 1)
    with pytest.raises(ValidationError):
        OperationAuditLogCreate(**values)

    values[field_name] = " "
    with pytest.raises(ValidationError):
        OperationAuditLogCreate(**values)


def test_operation_audit_log_query_scope_is_explicit_and_isolated():
    suffix = uuid4().hex[:8]
    project_codes = [f"AUDIT_SCOPE_A_{suffix}", f"AUDIT_SCOPE_B_{suffix}"]
    actor_name = f"scope_actor_{suffix}"
    services = create_database_services()
    timestamp = datetime(2026, 9, 7, 8, 0, 0)
    try:
        for project_code in project_codes:
            services.projects.create(ProjectCreate(
                project_code=project_code,
                project_name=project_code,
            ))
        system_log = services.audit_logs.record(OperationAuditLogCreate(
            actor_name=actor_name,
            action_code="SYSTEM_ACTION",
            resource_type="SYSTEM",
            result_code="SUCCESS",
            request_id=f"scope-system-{suffix}",
            occurred_at=timestamp,
        ))
        project_logs = [
            services.audit_logs.record(OperationAuditLogCreate(
                project_code=project_code,
                actor_name=actor_name,
                action_code="PROJECT_ACTION",
                resource_type="PROJECT",
                resource_code=project_code,
                result_code="SUCCESS",
                request_id=f"scope-{index}-{suffix}",
                occurred_at=timestamp,
            ))
            for index, project_code in enumerate(project_codes)
        ]

        system_page = services.audit_logs.list(OperationAuditLogFilter(
            scope=OperationAuditLogScope.SYSTEM,
            actor_name=actor_name,
        ))
        assert [item.id for item in system_page.items] == [system_log.id]

        project_page = services.audit_logs.list(OperationAuditLogFilter(
            scope=OperationAuditLogScope.PROJECT,
            project_code=project_codes[0],
            actor_name=actor_name,
        ))
        assert [item.id for item in project_page.items] == [project_logs[0].id]

        all_page = services.audit_logs.list(OperationAuditLogFilter(
            scope=OperationAuditLogScope.ALL,
            actor_name=actor_name,
        ))
        assert {item.id for item in all_page.items} == {
            system_log.id,
            project_logs[0].id,
            project_logs[1].id,
        }

        with pytest.raises(OperationAuditLogNotFoundError):
            services.audit_logs.get(
                project_logs[1].id,
                scope=OperationAuditLogScope.PROJECT,
                project_code=project_codes[0],
            )
        assert services.audit_logs.get(
            system_log.id, scope=OperationAuditLogScope.SYSTEM
        ).id == system_log.id
        assert services.audit_logs.get(
            project_logs[1].id, scope=OperationAuditLogScope.ALL
        ).id == project_logs[1].id

        with pytest.raises(InvalidDataError):
            services.audit_logs.get(
                system_log.id, scope=OperationAuditLogScope.PROJECT
            )
        with pytest.raises(InvalidDataError):
            services.audit_logs.get(
                system_log.id,
                scope=OperationAuditLogScope.SYSTEM,
                project_code=project_codes[0],
            )
        with pytest.raises(ProjectNotFoundError):
            services.audit_logs.list(OperationAuditLogFilter(
                scope=OperationAuditLogScope.PROJECT,
                project_code=f"MISSING_{suffix}",
            ))
    finally:
        _cleanup(suffix)


def test_operation_audit_log_default_sort_is_stable_for_equal_times():
    suffix = uuid4().hex[:8]
    actor_name = f"sort_actor_{suffix}"
    services = create_database_services()
    timestamp = datetime(2026, 9, 7, 8, 0, 0)
    try:
        created = [
            services.audit_logs.record(OperationAuditLogCreate(
                actor_name=actor_name,
                action_code="SORT_TEST",
                resource_type="SYSTEM",
                result_code="SUCCESS",
                request_id=f"sort-{index}-{suffix}",
                occurred_at=timestamp,
            ))
            for index in range(3)
        ]
        page = services.audit_logs.list(OperationAuditLogFilter(
            scope=OperationAuditLogScope.SYSTEM,
            actor_name=actor_name,
        ))
        assert [item.id for item in page.items] == sorted(
            (item.id for item in created), reverse=True
        )
    finally:
        _cleanup(suffix)


def test_operation_audit_log_record_rolls_back_after_flush(monkeypatch):
    from backend_db.services import operation_audit_log as audit_service_module

    suffix = uuid4().hex[:8]
    request_id = f"rollback-{suffix}"
    services = create_database_services()

    def fail_after_flush(*_args):
        raise RuntimeError("forced failure after flush")

    monkeypatch.setattr(audit_service_module, "_to_read", fail_after_flush)
    with pytest.raises(RuntimeError, match="forced failure"):
        services.audit_logs.record(OperationAuditLogCreate(
            action_code="ROLLBACK_TEST",
            resource_type="SYSTEM",
            result_code="FAILURE",
            request_id=request_id,
            occurred_at=datetime(2026, 9, 7, 8, 0, 0),
        ))

    with SessionLocal() as session:
        assert session.query(OperationAuditLog).filter_by(
            request_id=request_id
        ).count() == 0
