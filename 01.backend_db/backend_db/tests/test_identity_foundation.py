from datetime import datetime

import pytest
from pydantic import ValidationError

from backend_db.models import AppUser
from backend_db.schemas import (
    PermissionCreate,
    RoleCreate,
    RoleScope,
    UserAuthRecord,
    UserCreate,
    UserRead,
)


def test_user_create_accepts_hash_but_rejects_plaintext_and_weak_values():
    data = UserCreate(
        username="  operator01  ",
        display_name="  操作员  ",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$example",
    )
    assert data.username == "operator01"
    assert data.display_name == "操作员"

    with pytest.raises(ValidationError):
        UserCreate(
            username="operator01",
            display_name="操作员",
            password_hash="short",
        )
    with pytest.raises(ValidationError):
        UserCreate(
            username="operator01",
            display_name="操作员",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$example",
            password="plaintext",
        )


def test_normal_user_read_never_contains_password_hash():
    timestamp = datetime(2026, 9, 4, 6, 0, 0)
    user = AppUser(
        id=1,
        username="operator01",
        display_name="操作员",
        is_active=True,
        remark=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = UserRead.model_validate(user)
    assert "password_hash" not in result.model_dump()


def test_auth_record_is_a_separate_explicit_contract():
    timestamp = datetime(2026, 9, 4, 6, 0, 0)
    record = UserAuthRecord(
        user_id=1,
        username="operator01",
        display_name="操作员",
        is_active=True,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$example",
        password_changed_at=timestamp,
    )
    assert record.password_hash.startswith("$argon2id$")


def test_role_and_permission_codes_are_typed_and_extra_fields_forbidden():
    role = RoleCreate(
        role_code="PROJECT_OPERATOR",
        role_name="项目操作员",
        role_scope=RoleScope.PROJECT,
    )
    permission = PermissionCreate(
        permission_code="beam.view",
        permission_name="查看梁",
        module_code="beam",
    )
    assert role.role_scope is RoleScope.PROJECT
    assert permission.permission_code == "beam.view"

    with pytest.raises(ValidationError):
        RoleCreate(
            role_code="INVALID",
            role_name="非法角色",
            role_scope="GLOBAL",
        )
