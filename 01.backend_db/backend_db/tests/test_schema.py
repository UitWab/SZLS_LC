from sqlalchemy import inspect

from backend_db.database.mysql import engine


def _unique_columns(inspector, table_name: str) -> set[tuple[str, ...]]:
    """
    统一读取 UNIQUE 约束。

    MySQL 中 UNIQUE 可能以唯一索引形式被 SQLAlchemy Inspector 返回，
    因此同时检查 unique_constraints 和 indexes。
    """
    result: set[tuple[str, ...]] = set()

    for constraint in inspector.get_unique_constraints(table_name):
        columns = constraint.get("column_names") or []
        result.add(tuple(columns))

    for index in inspector.get_indexes(table_name):
        if index.get("unique"):
            columns = index.get("column_names") or []
            result.add(tuple(columns))

    return result


def _foreign_keys(inspector, table_name: str) -> dict[str, str]:
    """
    返回：
    外键字段名 -> 被引用表名
    """
    result = {}

    for foreign_key in inspector.get_foreign_keys(table_name):
        columns = foreign_key.get("constrained_columns") or []

        if len(columns) == 1:
            result[columns[0]] = foreign_key["referred_table"]

    return result


def test_core_tables_exist():
    """检查梁场基础域核心表是否全部存在。"""

    inspector = inspect(engine)

    actual_tables = set(inspector.get_table_names())

    expected_tables = {
        "app_user",
        "auth_permission",
        "auth_role",
        "auth_role_permission",
        "auth_user_role",
        "project",
        "project_member",
        "project_member_role",
        "process_definition",
        "operation_audit_log",
        "beam_position_work_order",
        "beam_lifecycle_event",
        "beam_lifecycle_event_stream_lock",
        "beam_process_execution",
        "user_credential",
        "yard_area",
        "beam_type",
        "beam_position",
        "beam",
    }

    assert expected_tables.issubset(actual_tables)


def test_identity_access_schema():
    inspector = inspect(engine)

    user_columns = {
        column["name"]: column
        for column in inspector.get_columns("app_user")
    }
    assert "password_hash" not in user_columns
    assert ("username",) in _unique_columns(inspector, "app_user")

    credential_columns = {
        column["name"]: column
        for column in inspector.get_columns("user_credential")
    }
    assert set(credential_columns) == {
        "user_id",
        "password_hash",
        "password_changed_at",
        "created_at",
        "updated_at",
    }
    assert _foreign_keys(inspector, "user_credential")["user_id"] == "app_user"

    assert ("role_code",) in _unique_columns(inspector, "auth_role")
    assert ("permission_code",) in _unique_columns(
        inspector,
        "auth_permission",
    )

    role_permission_pk = inspector.get_pk_constraint("auth_role_permission")
    assert set(role_permission_pk["constrained_columns"]) == {
        "role_id",
        "permission_id",
    }
    role_permission_fks = _foreign_keys(inspector, "auth_role_permission")
    assert role_permission_fks == {
        "role_id": "auth_role",
        "permission_id": "auth_permission",
    }


def test_project_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("project")
    }
    assert set(columns) == {
        "id",
        "project_code",
        "project_name",
        "is_active",
        "remark",
        "created_at",
        "updated_at",
    }
    assert columns["project_code"]["nullable"] is False
    assert ("project_code",) in _unique_columns(inspector, "project")


def test_process_definition_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("process_definition")
    }
    assert set(columns) == {
        "id",
        "project_id",
        "process_code",
        "process_name",
        "sort_order",
        "is_active",
        "remark",
        "created_at",
        "updated_at",
    }
    assert columns["project_id"]["nullable"] is True
    assert ("process_code",) in _unique_columns(inspector, "process_definition")
    assert _foreign_keys(inspector, "process_definition")["project_id"] == "project"


def test_operation_audit_log_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("operation_audit_log")
    }
    assert set(columns) == {
        "id",
        "project_id",
        "actor_user_id",
        "actor_name",
        "action_code",
        "resource_type",
        "resource_code",
        "result_code",
        "request_id",
        "source",
        "summary",
        "occurred_at",
        "created_at",
    }
    assert columns["project_id"]["nullable"] is True
    assert columns["actor_user_id"]["nullable"] is True
    assert columns["action_code"]["nullable"] is False
    assert columns["occurred_at"]["nullable"] is False
    assert _foreign_keys(inspector, "operation_audit_log") == {
        "actor_user_id": "app_user",
        "project_id": "project",
    }


def test_beam_position_work_order_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_position_work_order")
    }
    assert set(columns) == {
        "id",
        "project_id",
        "work_order_code",
        "order_type",
        "beam_id",
        "source_position_id",
        "target_position_id",
        "status",
        "planned_at",
        "started_at",
        "finished_at",
        "remark",
        "created_at",
        "updated_at",
    }
    assert columns["project_id"]["nullable"] is True
    assert columns["beam_id"]["nullable"] is False
    assert columns["source_position_id"]["nullable"] is True
    assert columns["target_position_id"]["nullable"] is True
    assert columns["status"]["nullable"] is False
    assert ("work_order_code",) in _unique_columns(
        inspector, "beam_position_work_order"
    )
    assert _foreign_keys(inspector, "beam_position_work_order") == {
        "project_id": "project",
        "beam_id": "beam",
        "source_position_id": "beam_position",
        "target_position_id": "beam_position",
    }
    indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("beam_position_work_order")
    }
    assert indexes["ix_bpw_order_project_status_id"] == (
        "project_id",
        "status",
        "id",
    )
    assert indexes["ix_bpw_order_beam_status"] == ("beam_id", "status")


def test_beam_lifecycle_event_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_lifecycle_event")
    }
    assert set(columns) == {
        "id",
        "project_id",
        "beam_id",
        "event_type",
        "status_before",
        "status_after",
        "source_position_id",
        "target_position_id",
        "work_order_id",
        "occurred_at",
        "created_at",
    }
    assert columns["project_id"]["nullable"] is True
    assert columns["beam_id"]["nullable"] is False
    assert columns["event_type"]["nullable"] is False
    assert columns["occurred_at"]["nullable"] is False
    assert _foreign_keys(inspector, "beam_lifecycle_event") == {
        "project_id": "project",
        "beam_id": "beam",
        "source_position_id": "beam_position",
        "target_position_id": "beam_position",
        "work_order_id": "beam_position_work_order",
    }
    indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("beam_lifecycle_event")
    }
    assert indexes["ix_beam_event_project_occurred_id"] == (
        "project_id",
        "occurred_at",
        "id",
    )
    assert indexes["ix_beam_event_beam_occurred_id"] == (
        "beam_id",
        "occurred_at",
        "id",
    )
    assert indexes["ix_beam_event_project_id"] == (
        "project_id",
        "id",
    )


def test_beam_lifecycle_event_stream_lock_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_lifecycle_event_stream_lock")
    }
    assert set(columns) == {"scope_key"}
    assert columns["scope_key"]["nullable"] is False
    assert inspector.get_pk_constraint(
        "beam_lifecycle_event_stream_lock"
    )["constrained_columns"] == ["scope_key"]
    assert _foreign_keys(inspector, "beam_lifecycle_event_stream_lock") == {}


def test_beam_process_execution_schema():
    inspector = inspect(engine)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_process_execution")
    }
    assert set(columns) == {
        "id",
        "project_id",
        "execution_code",
        "beam_id",
        "process_definition_id",
        "result_code",
        "started_at",
        "finished_at",
        "actor_user_id",
        "actor_name",
        "source",
        "external_record_id",
        "supersedes_execution_id",
        "remark",
        "is_voided",
        "voided_at",
        "voided_by_user_id",
        "voided_by_name",
        "void_reason",
        "created_at",
        "updated_at",
    }
    assert columns["project_id"]["nullable"] is True
    assert columns["execution_code"]["nullable"] is False
    assert columns["finished_at"]["nullable"] is False
    assert columns["is_voided"]["nullable"] is False
    assert _foreign_keys(inspector, "beam_process_execution") == {
        "project_id": "project",
        "beam_id": "beam",
        "process_definition_id": "process_definition",
        "actor_user_id": "app_user",
        "voided_by_user_id": "app_user",
        "supersedes_execution_id": "beam_process_execution",
    }
    unique_columns = _unique_columns(inspector, "beam_process_execution")
    assert ("execution_code",) in unique_columns
    assert ("source", "external_record_id") in unique_columns
    assert ("supersedes_execution_id",) in unique_columns
    check_names = {
        item["name"] for item in inspector.get_check_constraints(
            "beam_process_execution"
        )
    }
    assert {
        "ck_beam_process_execution_time_order",
        "ck_beam_process_execution_void_fields",
    }.issubset(check_names)
    indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("beam_process_execution")
    }
    assert indexes["ix_beam_process_execution_project_finished_id"] == (
        "project_id", "finished_at", "id"
    )
    assert indexes["ix_beam_process_execution_beam_finished_id"] == (
        "beam_id", "finished_at", "id"
    )
    assert indexes["ix_beam_process_execution_process_finished_id"] == (
        "process_definition_id", "finished_at", "id"
    )


def test_yard_area_schema():
    inspector = inspect(engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns("yard_area")
    }

    assert set(columns) == {
        "id",
        "project_id",
        "area_code",
        "area_name",
        "area_type",
        "parent_id",
        "sort_order",
        "is_active",
        "remark",
        "created_at",
        "updated_at",
    }

    assert columns["id"]["nullable"] is False
    assert columns["area_code"]["nullable"] is False
    assert columns["parent_id"]["nullable"] is True

    pk = inspector.get_pk_constraint("yard_area")
    assert pk["constrained_columns"] == ["id"]

    unique_columns = _unique_columns(inspector, "yard_area")
    assert ("area_code",) in unique_columns

    foreign_keys = _foreign_keys(inspector, "yard_area")
    assert foreign_keys["parent_id"] == "yard_area"
    assert foreign_keys["project_id"] == "project"
    assert columns["project_id"]["nullable"] is True


def test_beam_type_schema():
    inspector = inspect(engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_type")
    }

    assert set(columns) == {
        "id",
        "project_id",
        "type_code",
        "type_name",
        "length_mm",
        "width_mm",
        "height_mm",
        "weight_kg",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }

    pk = inspector.get_pk_constraint("beam_type")
    assert pk["constrained_columns"] == ["id"]

    unique_columns = _unique_columns(inspector, "beam_type")
    assert ("type_code",) in unique_columns
    assert _foreign_keys(inspector, "beam_type")["project_id"] == "project"
    assert columns["project_id"]["nullable"] is True


def test_beam_position_schema():
    inspector = inspect(engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam_position")
    }

    assert set(columns) == {
        "id",
        "position_code",
        "position_name",
        "area_id",
        "x_mm",
        "y_mm",
        "z_mm",
        "is_active",
        "remark",
        "created_at",
        "updated_at",
    }

    assert columns["area_id"]["nullable"] is False
    assert columns["position_name"]["nullable"] is True

    unique_columns = _unique_columns(inspector, "beam_position")
    assert ("position_code",) in unique_columns

    foreign_keys = _foreign_keys(inspector, "beam_position")
    assert foreign_keys["area_id"] == "yard_area"


def test_beam_schema():
    inspector = inspect(engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns("beam")
    }

    assert set(columns) == {
        "id",
        "project_id",
        "beam_code",
        "beam_name",
        "beam_type_id",
        "current_position_id",
        "status",
        "production_date",
        "remark",
        "created_at",
        "updated_at",
    }

    assert columns["beam_type_id"]["nullable"] is False
    assert columns["current_position_id"]["nullable"] is True
    assert columns["status"]["nullable"] is False

    pk = inspector.get_pk_constraint("beam")
    assert pk["constrained_columns"] == ["id"]

    unique_columns = _unique_columns(inspector, "beam")

    assert ("beam_code",) in unique_columns
    assert ("current_position_id",) in unique_columns

    foreign_keys = _foreign_keys(inspector, "beam")

    assert foreign_keys["beam_type_id"] == "beam_type"
    assert foreign_keys["current_position_id"] == "beam_position"
    assert foreign_keys["project_id"] == "project"
    assert columns["project_id"]["nullable"] is True
