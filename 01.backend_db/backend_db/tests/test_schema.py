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
