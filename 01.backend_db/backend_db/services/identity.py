from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.identity import (
    assign_role_permission,
    assign_project_role,
    assign_system_role,
    create_project_member,
    create_permission,
    create_role,
    create_user_with_credential,
    get_permission_by_code,
    get_role_by_code,
    get_user,
    get_user_by_username,
    get_project_member,
    list_permissions,
    list_project_members,
    list_roles,
    list_role_permissions,
    list_effective_permission_codes,
    list_member_role_codes,
    list_member_role_codes_by_member_ids,
    list_user_role_codes,
    list_users,
    revoke_project_role,
    revoke_role_permission,
    revoke_system_role,
    set_permission_active,
    set_project_member_active,
    set_role_active,
    set_password_hash,
    set_user_active,
    update_user,
    update_permission,
    update_role,
)
from backend_db.crud.project import get_project_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    PermissionNotFoundError,
    InactiveResourceError,
    InvalidDataError,
    ProjectNotFoundError,
    ResourceAlreadyExistsError,
    RoleNotFoundError,
    UserCredentialNotFoundError,
    UserNotFoundError,
)
from backend_db.schemas import (
    PageRequest,
    PageResult,
    PasswordHashUpdate,
    PermissionCreate,
    PermissionFilter,
    PermissionRead,
    PermissionSortField,
    PermissionUpdate,
    EffectivePermissionSet,
    RoleCreate,
    RoleFilter,
    RolePermissionCommand,
    RoleRead,
    RoleAssignmentCommand,
    RoleScope,
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
)
from backend_db.services._errors import raise_database_error


class UserService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: UserCreate) -> UserRead:
        try:
            with self._unit_of_work_factory() as unit:
                user = create_user_with_credential(unit.session, **data.model_dump())
                result = UserRead.model_validate(user)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(f"用户名已存在: {data.username}") from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, user_id: int) -> UserRead:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user(unit.session, user_id)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: id={user_id}")
                return UserRead.model_validate(user)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get_auth_record(self, username: str) -> UserAuthRecord:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user_by_username(unit.session, username, with_credential=True)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                if user.credential is None:
                    raise UserCredentialNotFoundError("用户没有密码凭据")
                return UserAuthRecord(
                    user_id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    is_active=user.is_active,
                    password_hash=user.credential.password_hash,
                    password_changed_at=user.credential.password_changed_at,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(self, filters=None, page_request=None, *, sort_by=UserSortField.ID,
             sort_order=SortOrder.ASC) -> PageResult[UserRead]:
        filters = filters or UserFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_users(
                    unit.session,
                    **filters.model_dump(exclude_none=True),
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[UserRead](
                    items=[UserRead.model_validate(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update(self, user_id: int, data: UserUpdate) -> UserRead:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user(unit.session, user_id)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: id={user_id}")
                changes = data.model_dump(exclude_unset=True)
                if changes:
                    update_user(unit.session, user, changes)
                result = UserRead.model_validate(user)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(self, user_id: int, *, is_active: bool) -> UserRead:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user(unit.session, user_id)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: id={user_id}")
                set_user_active(unit.session, user, is_active=is_active)
                result = UserRead.model_validate(user)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update_password_hash(self, user_id: int, data: PasswordHashUpdate) -> None:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user(unit.session, user_id, with_credential=True)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: id={user_id}")
                if user.credential is None:
                    raise UserCredentialNotFoundError("用户没有密码凭据")
                set_password_hash(unit.session, user.credential,
                                  password_hash=data.password_hash)
                unit.commit()
        except SQLAlchemyError as error:
            raise_database_error(error)


class AccessControlService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create_role(self, data: RoleCreate) -> RoleRead:
        try:
            with self._unit_of_work_factory() as unit:
                values = data.model_dump(mode="python")
                values["role_scope"] = data.role_scope.value
                role = create_role(unit.session, **values)
                result = RoleRead.model_validate(role)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(f"角色编码已存在: {data.role_code}") from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def create_permission(self, data: PermissionCreate) -> PermissionRead:
        try:
            with self._unit_of_work_factory() as unit:
                permission = create_permission(unit.session, **data.model_dump())
                result = PermissionRead.model_validate(permission)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"权限编码已存在: {data.permission_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get_role(self, role_code: str) -> RoleRead:
        try:
            with self._unit_of_work_factory() as unit:
                role = get_role_by_code(unit.session, role_code)
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                return RoleRead.model_validate(role)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list_roles(
        self,
        filters: RoleFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: RoleSortField = RoleSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[RoleRead]:
        filters = filters or RoleFilter()
        page_request = page_request or PageRequest()
        values = filters.model_dump(exclude_none=True, mode="python")
        if "role_scope" in values:
            values["role_scope"] = values["role_scope"].value
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_roles(
                    unit.session,
                    **values,
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[RoleRead](
                    items=[RoleRead.model_validate(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update_role(self, role_code: str, data: RoleUpdate) -> RoleRead:
        try:
            with self._unit_of_work_factory() as unit:
                role = get_role_by_code(unit.session, role_code)
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                changes = data.model_dump(exclude_unset=True)
                if changes:
                    update_role(unit.session, role, changes)
                result = RoleRead.model_validate(role)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_role_active(self, role_code: str, *, is_active: bool) -> RoleRead:
        try:
            with self._unit_of_work_factory() as unit:
                role = get_role_by_code(unit.session, role_code)
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                set_role_active(unit.session, role, is_active=is_active)
                result = RoleRead.model_validate(role)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get_permission(self, permission_code: str) -> PermissionRead:
        try:
            with self._unit_of_work_factory() as unit:
                permission = get_permission_by_code(unit.session, permission_code)
                if permission is None:
                    raise PermissionNotFoundError(
                        f"权限不存在: permission_code={permission_code}"
                    )
                return PermissionRead.model_validate(permission)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list_permission_catalog(
        self,
        filters: PermissionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: PermissionSortField = PermissionSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[PermissionRead]:
        filters = filters or PermissionFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_permissions(
                    unit.session,
                    **filters.model_dump(exclude_none=True),
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[PermissionRead](
                    items=[PermissionRead.model_validate(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update_permission(
        self,
        permission_code: str,
        data: PermissionUpdate,
    ) -> PermissionRead:
        try:
            with self._unit_of_work_factory() as unit:
                permission = get_permission_by_code(unit.session, permission_code)
                if permission is None:
                    raise PermissionNotFoundError(
                        f"权限不存在: permission_code={permission_code}"
                    )
                changes = data.model_dump(exclude_unset=True)
                if changes:
                    update_permission(unit.session, permission, changes)
                result = PermissionRead.model_validate(permission)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_permission_active(
        self,
        permission_code: str,
        *,
        is_active: bool,
    ) -> PermissionRead:
        try:
            with self._unit_of_work_factory() as unit:
                permission = get_permission_by_code(unit.session, permission_code)
                if permission is None:
                    raise PermissionNotFoundError(
                        f"权限不存在: permission_code={permission_code}"
                    )
                set_permission_active(unit.session, permission, is_active=is_active)
                result = PermissionRead.model_validate(permission)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def assign_permission(self, role_code: str, data: RolePermissionCommand) -> list[PermissionRead]:
        return self._change_permission(role_code, data.permission_code, revoke=False)

    def revoke_permission(self, role_code: str, data: RolePermissionCommand) -> list[PermissionRead]:
        return self._change_permission(role_code, data.permission_code, revoke=True)

    def _change_permission(self, role_code: str, permission_code: str, *, revoke: bool):
        try:
            with self._unit_of_work_factory() as unit:
                role = get_role_by_code(unit.session, role_code, for_update=True)
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                permission = get_permission_by_code(unit.session, permission_code)
                if permission is None:
                    raise PermissionNotFoundError(
                        f"权限不存在: permission_code={permission_code}"
                    )
                operation = revoke_role_permission if revoke else assign_role_permission
                operation(unit.session, role, permission)
                result = [PermissionRead.model_validate(item)
                          for item in list_role_permissions(unit.session, role.id)]
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list_permissions(self, role_code: str) -> list[PermissionRead]:
        try:
            with self._unit_of_work_factory() as unit:
                role = get_role_by_code(unit.session, role_code)
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                return [PermissionRead.model_validate(item)
                        for item in list_role_permissions(unit.session, role.id)]
        except SQLAlchemyError as error:
            raise_database_error(error)

    def assign_system_role(self, username: str, data: RoleAssignmentCommand) -> list[str]:
        return self._change_system_role(username, data.role_code, revoke=False)

    def revoke_system_role(self, username: str, data: RoleAssignmentCommand) -> list[str]:
        return self._change_system_role(username, data.role_code, revoke=True)

    def _change_system_role(
        self,
        username: str,
        role_code: str,
        *,
        revoke: bool,
    ) -> list[str]:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user_by_username(unit.session, username)
                role = get_role_by_code(unit.session, role_code, for_update=True)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                if not revoke and (not user.is_active or not role.is_active):
                    raise InactiveResourceError("用户或角色未启用")
                if role.role_scope != RoleScope.SYSTEM.value:
                    raise InvalidDataError("项目级角色不能分配为系统角色")
                operation = revoke_system_role if revoke else assign_system_role
                operation(unit.session, user, role)
                result = list_user_role_codes(unit.session, user.id)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list_system_role_codes(self, username: str) -> list[str]:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user_by_username(unit.session, username)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                return list_user_role_codes(unit.session, user.id)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def add_project_member(
        self,
        project_code: str,
        data: ProjectMemberCreate,
    ) -> ProjectMemberRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project_by_code(unit.session, project_code, for_update=True)
                user = get_user_by_username(unit.session, data.username)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={data.username}")
                if not project.is_active or not user.is_active:
                    raise InactiveResourceError("项目或用户未启用")
                member = get_project_member(unit.session, project.id, user.id)
                if member is None:
                    member = create_project_member(unit.session, project.id, user.id)
                elif not member.is_active:
                    member.is_active = True
                    unit.session.flush()
                result = ProjectMemberRead(
                    id=member.id,
                    project_code=project.project_code,
                    username=user.username,
                    is_active=member.is_active,
                    role_codes=list_member_role_codes(unit.session, member.id),
                )
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def assign_project_role(
        self,
        project_code: str,
        username: str,
        data: RoleAssignmentCommand,
    ) -> ProjectMemberRead:
        return self._change_project_role(
            project_code, username, data.role_code, revoke=False
        )

    def _change_project_role(
        self,
        project_code: str,
        username: str,
        role_code: str,
        *,
        revoke: bool,
    ) -> ProjectMemberRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project_by_code(unit.session, project_code)
                user = get_user_by_username(unit.session, username)
                role = get_role_by_code(unit.session, role_code, for_update=True)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                if role is None:
                    raise RoleNotFoundError(f"角色不存在: role_code={role_code}")
                member = get_project_member(unit.session, project.id, user.id)
                if member is None:
                    raise InvalidDataError("用户不是项目成员")
                if not revoke and not member.is_active:
                    raise InvalidDataError("用户不是有效项目成员")
                if not revoke and (
                    not project.is_active or not user.is_active or not role.is_active
                ):
                    raise InactiveResourceError("项目、用户或角色未启用")
                if role.role_scope != RoleScope.PROJECT.value:
                    raise InvalidDataError("系统级角色不能分配为项目角色")
                operation = revoke_project_role if revoke else assign_project_role
                operation(unit.session, member, role)
                result = ProjectMemberRead(
                    id=member.id,
                    project_code=project_code,
                    username=username,
                    is_active=member.is_active,
                    role_codes=list_member_role_codes(unit.session, member.id),
                )
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def revoke_project_role(
        self,
        project_code: str,
        username: str,
        data: RoleAssignmentCommand,
    ) -> ProjectMemberRead:
        return self._change_project_role(
            project_code, username, data.role_code, revoke=True
        )

    def list_project_members(
        self,
        project_code: str,
        filters: ProjectMemberFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProjectMemberSortField = ProjectMemberSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProjectMemberRead]:
        filters = filters or ProjectMemberFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project_by_code(unit.session, project_code)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
                rows, total, has_next = list_project_members(
                    unit.session,
                    project.id,
                    **filters.model_dump(exclude_none=True),
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                role_codes_by_member = list_member_role_codes_by_member_ids(
                    unit.session,
                    [member.id for member, _ in rows],
                )
                return PageResult[ProjectMemberRead](
                    items=[ProjectMemberRead(
                        id=member.id,
                        project_code=project.project_code,
                        username=username,
                        is_active=member.is_active,
                        role_codes=role_codes_by_member[member.id],
                    ) for member, username in rows],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_project_member_active(
        self,
        project_code: str,
        username: str,
        *,
        is_active: bool,
    ) -> ProjectMemberRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project_by_code(unit.session, project_code)
                user = get_user_by_username(unit.session, username)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                member = get_project_member(unit.session, project.id, user.id)
                if member is None:
                    raise InvalidDataError("用户不是项目成员")
                if is_active and (not project.is_active or not user.is_active):
                    raise InactiveResourceError("停用的项目或用户不能启用成员关系")
                set_project_member_active(unit.session, member, is_active=is_active)
                result = ProjectMemberRead(
                    id=member.id,
                    project_code=project_code,
                    username=username,
                    is_active=member.is_active,
                    role_codes=list_member_role_codes(unit.session, member.id),
                )
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get_effective_permissions(
        self,
        username: str,
        *,
        project_code: str | None = None,
    ) -> EffectivePermissionSet:
        try:
            with self._unit_of_work_factory() as unit:
                user = get_user_by_username(unit.session, username)
                if user is None:
                    raise UserNotFoundError(f"用户不存在: username={username}")
                if not user.is_active:
                    raise InactiveResourceError("用户未启用")
                member_id = None
                if project_code is not None:
                    project = get_project_by_code(unit.session, project_code)
                    if project is None:
                        raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
                    member = get_project_member(unit.session, project.id, user.id)
                    if member is not None and member.is_active and project.is_active:
                        member_id = member.id
                return EffectivePermissionSet(
                    user_id=user.id,
                    username=user.username,
                    project_code=project_code,
                    permission_codes=list_effective_permission_codes(
                        unit.session, user.id, member_id
                    ),
                )
        except SQLAlchemyError as error:
            raise_database_error(error)
