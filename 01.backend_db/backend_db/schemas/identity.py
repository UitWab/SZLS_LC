from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from backend_db.schemas.base import SchemaModel


Username = Annotated[str, Field(min_length=1, max_length=64)]
DisplayName = Annotated[str, Field(min_length=1, max_length=128)]
RoleCode = Annotated[str, Field(min_length=1, max_length=64)]
PermissionCode = Annotated[str, Field(min_length=1, max_length=128)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Description = Annotated[str, Field(max_length=500)]
PasswordHash = Annotated[str, Field(min_length=20, max_length=255)]


class RoleScope(StrEnum):
    SYSTEM = "SYSTEM"
    PROJECT = "PROJECT"


class UserCreate(SchemaModel):
    username: Username
    display_name: DisplayName
    password_hash: PasswordHash
    is_active: bool = True
    remark: Description | None = None


class UserUpdate(SchemaModel):
    display_name: DisplayName | None = None
    remark: Description | None = None

    @model_validator(mode="after")
    def validate_display_name_is_not_null(self):
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name 不能设置为 null")
        return self


class PasswordHashUpdate(SchemaModel):
    password_hash: PasswordHash


class UserRead(SchemaModel):
    id: int = Field(gt=0)
    username: str
    display_name: str
    is_active: bool
    remark: str | None
    created_at: datetime
    updated_at: datetime


class UserAuthRecord(SchemaModel):
    """只供 B 登录验证使用，不得作为普通用户响应。"""

    user_id: int = Field(gt=0)
    username: str
    display_name: str
    is_active: bool
    password_hash: str
    password_changed_at: datetime


class UserFilter(SchemaModel):
    username: Username | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class UserSortField(StrEnum):
    ID = "id"
    USERNAME = "username"
    DISPLAY_NAME = "display_name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class RoleCreate(SchemaModel):
    role_code: RoleCode
    role_name: Name
    role_scope: RoleScope
    is_active: bool = True
    description: Description | None = None


class RoleUpdate(SchemaModel):
    role_name: Name | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def validate_role_name_is_not_null(self):
        if "role_name" in self.model_fields_set and self.role_name is None:
            raise ValueError("role_name 不能设置为 null")
        return self


class RoleRead(SchemaModel):
    id: int = Field(gt=0)
    role_code: str
    role_name: str
    role_scope: RoleScope
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class RoleFilter(SchemaModel):
    role_code: RoleCode | None = None
    role_scope: RoleScope | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class RoleSortField(StrEnum):
    ID = "id"
    ROLE_CODE = "role_code"
    ROLE_NAME = "role_name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class RolePermissionCommand(SchemaModel):
    permission_code: PermissionCode


class RoleAssignmentCommand(SchemaModel):
    role_code: RoleCode


class ProjectMemberCreate(SchemaModel):
    username: Username


class ProjectMemberFilter(SchemaModel):
    username: Username | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class ProjectMemberSortField(StrEnum):
    ID = "id"
    USERNAME = "username"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class ProjectMemberRead(SchemaModel):
    id: int = Field(gt=0)
    project_code: str
    username: str
    is_active: bool
    role_codes: list[str]


class EffectivePermissionSet(SchemaModel):
    user_id: int = Field(gt=0)
    username: str
    project_code: str | None
    permission_codes: list[str]


class PermissionCreate(SchemaModel):
    permission_code: PermissionCode
    permission_name: Name
    module_code: Annotated[str, Field(min_length=1, max_length=64)]
    is_active: bool = True
    description: Description | None = None


class PermissionUpdate(SchemaModel):
    permission_name: Name | None = None
    module_code: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def validate_required_fields_are_not_null(self):
        for field_name in ("permission_name", "module_code"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能设置为 null")
        return self


class PermissionRead(SchemaModel):
    id: int = Field(gt=0)
    permission_code: str
    permission_name: str
    module_code: str
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class PermissionFilter(SchemaModel):
    permission_code: PermissionCode | None = None
    module_code: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    is_active: bool | None = None
    keyword: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class PermissionSortField(StrEnum):
    ID = "id"
    PERMISSION_CODE = "permission_code"
    PERMISSION_NAME = "permission_name"
    MODULE_CODE = "module_code"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
