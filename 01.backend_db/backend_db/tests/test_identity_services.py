from uuid import uuid4

from sqlalchemy import delete

from backend_db.database.mysql import SessionLocal
from backend_db.interfaces import (
    AccessControlServiceProtocol,
    UserServiceProtocol,
    create_database_services,
)
from backend_db.models import (
    AppUser,
    AuthPermission,
    AuthRole,
    AuthRolePermission,
    AuthUserRole,
    Project,
    ProjectMember,
    ProjectMemberRole,
    UserCredential,
)
from backend_db.schemas import (
    PageRequest,
    PasswordHashUpdate,
    PermissionCreate,
    PermissionFilter,
    PermissionUpdate,
    ProjectCreate,
    ProjectMemberCreate,
    RoleCreate,
    RoleFilter,
    RoleAssignmentCommand,
    RolePermissionCommand,
    RoleScope,
    RoleUpdate,
    UserCreate,
    UserFilter,
)


def test_user_service_keeps_auth_record_separate_and_updates_hash():
    suffix = uuid4().hex[:8]
    username = f"user_{suffix}"
    old_hash = "$argon2id$v=19$m=65536,t=3,p=4$old_hash_value"
    new_hash = "$argon2id$v=19$m=65536,t=3,p=4$new_hash_value"
    service = create_database_services().users
    try:
        created = service.create(UserCreate(
            username=username,
            display_name="测试用户",
            password_hash=old_hash,
        ))
        assert "password_hash" not in created.model_dump()
        assert service.get_auth_record(username).password_hash == old_hash
        service.update_password_hash(
            created.id,
            PasswordHashUpdate(password_hash=new_hash),
        )
        assert service.get_auth_record(username).password_hash == new_hash
        page = service.list(
            UserFilter(username=username),
            PageRequest(page=1, page_size=20),
        )
        assert len(page.items) == 1
        assert "password_hash" not in page.items[0].model_dump()
    finally:
        with SessionLocal.begin() as session:
            user = session.query(AppUser).filter_by(username=username).one_or_none()
            if user is not None:
                session.execute(delete(UserCredential).where(UserCredential.user_id == user.id))
                session.delete(user)


def test_access_control_assign_and_revoke_are_idempotent():
    suffix = uuid4().hex[:8]
    role_code = f"ROLE_{suffix}"
    permission_code = f"beam.view.{suffix}"
    service = create_database_services().access_control
    try:
        service.create_role(RoleCreate(
            role_code=role_code,
            role_name="测试角色",
            role_scope=RoleScope.PROJECT,
        ))
        service.create_permission(PermissionCreate(
            permission_code=permission_code,
            permission_name="查看梁",
            module_code="beam",
        ))
        command = RolePermissionCommand(permission_code=permission_code)
        assert [item.permission_code for item in service.assign_permission(role_code, command)] == [permission_code]
        assert len(service.assign_permission(role_code, command)) == 1
        assert service.revoke_permission(role_code, command) == []
        assert service.revoke_permission(role_code, command) == []
    finally:
        with SessionLocal.begin() as session:
            role = session.query(AuthRole).filter_by(role_code=role_code).one_or_none()
            permission = session.query(AuthPermission).filter_by(
                permission_code=permission_code
            ).one_or_none()
            if role is not None:
                session.execute(delete(AuthRolePermission).where(
                    AuthRolePermission.role_id == role.id
                ))
            if permission is not None:
                session.delete(permission)
            if role is not None:
                session.delete(role)


def test_role_and_permission_catalog_management():
    suffix = uuid4().hex[:8]
    role_code = f"CATALOG_ROLE_{suffix}"
    permission_code = f"catalog.manage.{suffix}"
    service = create_database_services().access_control
    try:
        service.create_role(RoleCreate(
            role_code=role_code,
            role_name="目录角色",
            role_scope=RoleScope.SYSTEM,
        ))
        service.create_permission(PermissionCreate(
            permission_code=permission_code,
            permission_name="目录权限",
            module_code="catalog",
        ))

        assert service.get_role(role_code).role_name == "目录角色"
        role_page = service.list_roles(
            RoleFilter(role_code=role_code, role_scope=RoleScope.SYSTEM),
            PageRequest(page_size=10),
        )
        assert [item.role_code for item in role_page.items] == [role_code]
        assert service.update_role(
            role_code, RoleUpdate(role_name="更新后的目录角色")
        ).role_name == "更新后的目录角色"
        assert service.set_role_active(role_code, is_active=False).is_active is False

        assert service.get_permission(permission_code).module_code == "catalog"
        permission_page = service.list_permission_catalog(
            PermissionFilter(module_code="catalog", permission_code=permission_code),
            PageRequest(page_size=10),
        )
        assert [item.permission_code for item in permission_page.items] == [
            permission_code
        ]
        assert service.update_permission(
            permission_code,
            PermissionUpdate(permission_name="更新后的目录权限", module_code="admin"),
        ).module_code == "admin"
        assert service.set_permission_active(
            permission_code, is_active=False
        ).is_active is False
    finally:
        with SessionLocal.begin() as session:
            role = session.query(AuthRole).filter_by(role_code=role_code).one_or_none()
            permission = session.query(AuthPermission).filter_by(
                permission_code=permission_code
            ).one_or_none()
            if role is not None:
                session.execute(delete(AuthRolePermission).where(
                    AuthRolePermission.role_id == role.id
                ))
            if permission is not None:
                session.delete(permission)
            if role is not None:
                session.delete(role)


def test_factory_exposes_identity_protocols():
    services = create_database_services()
    assert isinstance(services.users, UserServiceProtocol)
    assert isinstance(services.access_control, AccessControlServiceProtocol)


def test_effective_permissions_combine_system_and_project_roles():
    suffix = uuid4().hex[:8]
    username = f"member_{suffix}"
    project_code = f"PROJECT_{suffix}"
    system_role = f"SYS_{suffix}"
    project_role = f"PRJ_{suffix}"
    system_permission = f"system.view.{suffix}"
    project_permission = f"beam.manage.{suffix}"
    services = create_database_services()
    try:
        services.projects.create(ProjectCreate(
            project_code=project_code, project_name="权限测试项目"
        ))
        services.users.create(UserCreate(
            username=username,
            display_name="项目成员",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$member_hash_value",
        ))
        services.access_control.create_role(RoleCreate(
            role_code=system_role, role_name="系统角色", role_scope=RoleScope.SYSTEM
        ))
        services.access_control.create_role(RoleCreate(
            role_code=project_role, role_name="项目角色", role_scope=RoleScope.PROJECT
        ))
        for code in (system_permission, project_permission):
            services.access_control.create_permission(PermissionCreate(
                permission_code=code, permission_name=code, module_code="test"
            ))
        services.access_control.assign_permission(
            system_role, RolePermissionCommand(permission_code=system_permission)
        )
        services.access_control.assign_permission(
            project_role, RolePermissionCommand(permission_code=project_permission)
        )
        assert services.access_control.assign_system_role(
            username, RoleAssignmentCommand(role_code=system_role)
        ) == [system_role]
        assert services.access_control.list_system_role_codes(username) == [system_role]
        services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )
        member = services.access_control.assign_project_role(
            project_code, username, RoleAssignmentCommand(role_code=project_role)
        )
        assert member.role_codes == [project_role]
        result = services.access_control.get_effective_permissions(
            username, project_code=project_code
        )
        assert result.permission_codes == [project_permission, system_permission]

        members = services.access_control.list_project_members(
            project_code,
            page_request=PageRequest(page_size=10),
        )
        assert len(members.items) == 1
        assert members.items[0].role_codes == [project_role]

        inactive_member = services.access_control.set_project_member_active(
            project_code, username, is_active=False
        )
        assert inactive_member.is_active is False
        assert services.access_control.get_effective_permissions(
            username, project_code=project_code
        ).permission_codes == [system_permission]

        services.access_control.set_project_member_active(
            project_code, username, is_active=True
        )
        member = services.access_control.revoke_project_role(
            project_code,
            username,
            RoleAssignmentCommand(role_code=project_role),
        )
        assert member.role_codes == []
        assert services.access_control.revoke_system_role(
            username, RoleAssignmentCommand(role_code=system_role)
        ) == []
        assert services.access_control.get_effective_permissions(
            username, project_code=project_code
        ).permission_codes == []
    finally:
        with SessionLocal.begin() as session:
            user = session.query(AppUser).filter_by(username=username).one_or_none()
            project = session.query(Project).filter_by(project_code=project_code).one_or_none()
            roles = session.query(AuthRole).filter(
                AuthRole.role_code.in_([system_role, project_role])
            ).all()
            permissions = session.query(AuthPermission).filter(
                AuthPermission.permission_code.in_([system_permission, project_permission])
            ).all()
            if user is not None:
                members = session.query(ProjectMember).filter_by(user_id=user.id).all()
                for item in members:
                    session.execute(delete(ProjectMemberRole).where(
                        ProjectMemberRole.project_member_id == item.id
                    ))
                    session.delete(item)
                session.execute(delete(AuthUserRole).where(AuthUserRole.user_id == user.id))
                session.execute(delete(UserCredential).where(UserCredential.user_id == user.id))
                session.delete(user)
            for role in roles:
                session.execute(delete(AuthRolePermission).where(
                    AuthRolePermission.role_id == role.id
                ))
            for permission in permissions:
                session.delete(permission)
            for role in roles:
                session.delete(role)
            if project is not None:
                session.delete(project)
