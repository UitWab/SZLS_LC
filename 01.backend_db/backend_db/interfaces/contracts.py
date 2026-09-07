from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamPositionCommand,
    BeamPositionCreate,
    BeamPositionFilter,
    BeamPositionRead,
    BeamPositionSortField,
    BeamPositionSummary,
    BeamPositionUpdate,
    BeamRead,
    BeamSortField,
    BeamStatusChange,
    BeamSummary,
    BeamTypeCreate,
    BeamTypeFilter,
    BeamTypeRead,
    BeamTypeSortField,
    BeamTypeSummary,
    BeamTypeUpdate,
    BeamUpdate,
    PageRequest,
    PageResult,
    PasswordHashUpdate,
    EffectivePermissionSet,
    PermissionCreate,
    PermissionFilter,
    PermissionRead,
    PermissionSortField,
    PermissionUpdate,
    ProjectCreate,
    ProjectFilter,
    ProjectRead,
    ProjectSortField,
    ProjectSummary,
    ProjectUpdate,
    ProcessDefinitionCreate,
    ProcessDefinitionFilter,
    ProcessDefinitionRead,
    ProcessDefinitionSortField,
    ProcessDefinitionSummary,
    ProcessDefinitionUpdate,
    RoleCreate,
    RoleFilter,
    RoleAssignmentCommand,
    RolePermissionCommand,
    RoleRead,
    RoleSortField,
    RoleUpdate,
    SortOrder,
    UserAuthRecord,
    UserCreate,
    UserFilter,
    UserRead,
    UserSortField,
    UserUpdate,
    ProjectMemberCreate,
    ProjectMemberFilter,
    ProjectMemberRead,
    ProjectMemberSortField,
    YardAreaCreate,
    YardAreaFilter,
    YardAreaRead,
    YardAreaSortField,
    YardAreaSummary,
    YardAreaTreeNode,
    YardAreaUpdate,
)


@runtime_checkable
class UserServiceProtocol(Protocol):
    def create(self, data: UserCreate) -> UserRead: ...
    def get(self, user_id: int) -> UserRead: ...
    def get_auth_record(self, username: str) -> UserAuthRecord: ...
    def list(
        self,
        filters: UserFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: UserSortField = UserSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[UserRead]: ...
    def update(self, user_id: int, data: UserUpdate) -> UserRead: ...
    def set_active(self, user_id: int, *, is_active: bool) -> UserRead: ...
    def update_password_hash(self, user_id: int, data: PasswordHashUpdate) -> None: ...


@runtime_checkable
class AccessControlServiceProtocol(Protocol):
    def create_role(self, data: RoleCreate) -> RoleRead: ...
    def get_role(self, role_code: str) -> RoleRead: ...
    def list_roles(
        self,
        filters: RoleFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: RoleSortField = RoleSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[RoleRead]: ...
    def update_role(self, role_code: str, data: RoleUpdate) -> RoleRead: ...
    def set_role_active(self, role_code: str, *, is_active: bool) -> RoleRead: ...
    def create_permission(self, data: PermissionCreate) -> PermissionRead: ...
    def get_permission(self, permission_code: str) -> PermissionRead: ...
    def list_permission_catalog(
        self,
        filters: PermissionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: PermissionSortField = PermissionSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[PermissionRead]: ...
    def update_permission(self, permission_code: str, data: PermissionUpdate) -> PermissionRead: ...
    def set_permission_active(self, permission_code: str, *, is_active: bool) -> PermissionRead: ...
    def assign_permission(self, role_code: str, data: RolePermissionCommand) -> list[PermissionRead]: ...
    def revoke_permission(self, role_code: str, data: RolePermissionCommand) -> list[PermissionRead]: ...
    def list_permissions(self, role_code: str) -> list[PermissionRead]: ...
    def assign_system_role(self, username: str, data: RoleAssignmentCommand) -> list[str]: ...
    def revoke_system_role(self, username: str, data: RoleAssignmentCommand) -> list[str]: ...
    def list_system_role_codes(self, username: str) -> list[str]: ...
    def add_project_member(self, project_code: str, data: ProjectMemberCreate) -> ProjectMemberRead: ...
    def assign_project_role(self, project_code: str, username: str, data: RoleAssignmentCommand) -> ProjectMemberRead: ...
    def revoke_project_role(self, project_code: str, username: str, data: RoleAssignmentCommand) -> ProjectMemberRead: ...
    def list_project_members(
        self,
        project_code: str,
        filters: ProjectMemberFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProjectMemberSortField = ProjectMemberSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProjectMemberRead]: ...
    def set_project_member_active(self, project_code: str, username: str, *, is_active: bool) -> ProjectMemberRead: ...
    def get_effective_permissions(self, username: str, *, project_code: str | None = None) -> EffectivePermissionSet: ...


@runtime_checkable
class ProjectServiceProtocol(Protocol):
    def create(self, data: ProjectCreate) -> ProjectRead: ...
    def get(self, project_id: int) -> ProjectRead: ...
    def get_by_code(self, project_code: str) -> ProjectRead: ...
    def list(
        self,
        filters: ProjectFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProjectSortField = ProjectSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProjectSummary]: ...
    def update(self, project_id: int, data: ProjectUpdate) -> ProjectRead: ...
    def set_active(self, project_id: int, *, is_active: bool) -> ProjectRead: ...


@runtime_checkable
class ProcessDefinitionServiceProtocol(Protocol):
    def create(self, data: ProcessDefinitionCreate) -> ProcessDefinitionRead: ...
    def get(
        self,
        process_definition_id: int,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead: ...
    def get_by_code(
        self,
        process_code: str,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead: ...
    def list(
        self,
        filters: ProcessDefinitionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProcessDefinitionSortField = ProcessDefinitionSortField.SORT_ORDER,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProcessDefinitionSummary]: ...
    def update(
        self,
        process_definition_id: int,
        data: ProcessDefinitionUpdate,
        *,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead: ...
    def set_active(
        self,
        process_definition_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> ProcessDefinitionRead: ...


@runtime_checkable
class BeamTypeServiceProtocol(Protocol):
    def create(self, data: BeamTypeCreate) -> BeamTypeRead: ...
    def get(self, beam_type_id: int, *, project_code: str | None = None) -> BeamTypeRead: ...
    def get_by_code(self, type_code: str, *, project_code: str | None = None) -> BeamTypeRead: ...
    def list(
        self,
        filters: BeamTypeFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamTypeSortField = BeamTypeSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamTypeSummary]: ...
    def update(
        self,
        beam_type_id: int,
        data: BeamTypeUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamTypeRead: ...
    def set_active(
        self,
        beam_type_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> BeamTypeRead: ...


@runtime_checkable
class YardAreaServiceProtocol(Protocol):
    def create(self, data: YardAreaCreate) -> YardAreaRead: ...
    def get(self, area_id: int, *, project_code: str | None = None) -> YardAreaRead: ...
    def get_by_code(self, area_code: str, *, project_code: str | None = None) -> YardAreaRead: ...
    def list(
        self,
        filters: YardAreaFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: YardAreaSortField = YardAreaSortField.SORT_ORDER,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[YardAreaSummary]: ...
    def tree(
        self,
        *,
        is_active: bool | None = True,
        project_code: str | None = None,
        include_global: bool = False,
    ) -> list[YardAreaTreeNode]: ...
    def update(
        self,
        area_id: int,
        data: YardAreaUpdate,
        *,
        project_code: str | None = None,
    ) -> YardAreaRead: ...
    def set_active(
        self,
        area_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> YardAreaRead: ...


@runtime_checkable
class BeamPositionServiceProtocol(Protocol):
    def create(self, data: BeamPositionCreate) -> BeamPositionRead: ...
    def get(self, position_id: int, *, project_code: str | None = None) -> BeamPositionRead: ...
    def get_by_code(self, position_code: str, *, project_code: str | None = None) -> BeamPositionRead: ...
    def list(
        self,
        filters: BeamPositionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamPositionSortField = BeamPositionSortField.POSITION_CODE,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamPositionSummary]: ...
    def update(
        self,
        position_id: int,
        data: BeamPositionUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamPositionRead: ...
    def set_active(
        self,
        position_id: int,
        *,
        is_active: bool,
        project_code: str | None = None,
    ) -> BeamPositionRead: ...


@runtime_checkable
class BeamServiceProtocol(Protocol):
    def create(self, data: BeamCreate) -> BeamRead: ...
    def get(self, beam_id: int, *, project_code: str | None = None) -> BeamRead: ...
    def get_by_code(self, beam_code: str, *, project_code: str | None = None) -> BeamRead: ...
    def list(
        self,
        filters: BeamFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamSortField = BeamSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamSummary]: ...
    def update(
        self,
        beam_id: int,
        data: BeamUpdate,
        *,
        project_code: str | None = None,
    ) -> BeamRead: ...
    def change_status(
        self,
        beam_code: str,
        data: BeamStatusChange,
        *,
        project_code: str | None = None,
    ) -> BeamRead: ...
    def assign_position(
        self,
        beam_code: str,
        data: BeamPositionCommand,
        *,
        project_code: str | None = None,
    ) -> BeamRead: ...
    def move_beam(
        self,
        beam_code: str,
        data: BeamPositionCommand,
        *,
        project_code: str | None = None,
    ) -> BeamRead: ...
    def release_position(
        self, beam_code: str, *, project_code: str | None = None
    ) -> BeamRead: ...


@dataclass(frozen=True)
class DatabaseServices:
    projects: ProjectServiceProtocol
    processes: ProcessDefinitionServiceProtocol
    users: UserServiceProtocol
    access_control: AccessControlServiceProtocol
    beam_types: BeamTypeServiceProtocol
    yard_areas: YardAreaServiceProtocol
    beam_positions: BeamPositionServiceProtocol
    beams: BeamServiceProtocol
