from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event, or_

from backend_db.database.mysql import SessionLocal, engine
from backend_db.exceptions import (
    BeamNotFoundError,
    BeamPositionNotFoundError,
    BeamTypeNotFoundError,
    InactiveResourceError,
    InvalidDataError,
    ResourceAlreadyExistsError,
    ProcessDefinitionNotFoundError,
    YardAreaNotFoundError,
)
from backend_db.interfaces import create_database_services
from backend_db.models import (
    AppUser,
    Beam,
    BeamPosition,
    BeamType,
    AuthPermission,
    AuthRole,
    AuthRolePermission,
    AuthUserRole,
    ProcessDefinition,
    Project,
    ProjectMember,
    ProjectMemberRole,
    UserCredential,
    YardArea,
)
from backend_db.schemas import (
    BeamCreate,
    BeamPositionCommand,
    BeamPositionCreate,
    BeamTypeCreate,
    BeamTypeFilter,
    PageRequest,
    PermissionCreate,
    PermissionFilter,
    PermissionSortField,
    ProcessDefinitionFilter,
    ProcessDefinitionCreate,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberFilter,
    ProjectMemberSortField,
    RoleAssignmentCommand,
    RoleCreate,
    RoleFilter,
    RolePermissionCommand,
    RoleScope,
    RoleSortField,
    SortOrder,
    UserCreate,
    UserFilter,
    UserSortField,
    UserUpdate,
    YardAreaCreate,
)


def _hash(label: str) -> str:
    return f"$argon2id$v=19$m=65536,t=3,p=4${label}_hash_value"


def _cleanup(*, suffix: str) -> None:
    with SessionLocal.begin() as session:
        beams = session.query(Beam).filter(Beam.beam_code.contains(suffix)).all()
        positions = session.query(BeamPosition).filter(
            BeamPosition.position_code.contains(suffix)
        ).all()
        areas = session.query(YardArea).filter(YardArea.area_code.contains(suffix)).all()
        beam_types = session.query(BeamType).filter(
            BeamType.type_code.contains(suffix)
        ).all()
        users = session.query(AppUser).filter(AppUser.username.contains(suffix)).all()
        user_ids = [item.id for item in users]
        projects = session.query(Project).filter(Project.project_code.contains(suffix)).all()
        project_ids = [item.id for item in projects]
        roles = session.query(AuthRole).filter(AuthRole.role_code.contains(suffix)).all()
        role_ids = [item.id for item in roles]
        permissions = session.query(AuthPermission).filter(
            AuthPermission.permission_code.contains(suffix)
        ).all()
        permission_ids = [item.id for item in permissions]
        member_conditions = []
        if user_ids:
            member_conditions.append(ProjectMember.user_id.in_(user_ids))
        if project_ids:
            member_conditions.append(ProjectMember.project_id.in_(project_ids))
        members = (
            session.query(ProjectMember).filter(or_(*member_conditions)).all()
            if member_conditions
            else []
        )
        member_ids = [item.id for item in members]

        for item in beams:
            session.delete(item)
        for item in positions:
            session.delete(item)
        for item in areas:
            session.delete(item)
        for item in beam_types:
            session.delete(item)
        if member_ids:
            session.execute(delete(ProjectMemberRole).where(
                ProjectMemberRole.project_member_id.in_(member_ids)
            ))
        if user_ids:
            session.execute(delete(AuthUserRole).where(AuthUserRole.user_id.in_(user_ids)))
            session.execute(delete(UserCredential).where(UserCredential.user_id.in_(user_ids)))
        if role_ids:
            session.execute(delete(AuthRolePermission).where(
                AuthRolePermission.role_id.in_(role_ids)
            ))
        if permission_ids:
            session.execute(delete(AuthRolePermission).where(
                AuthRolePermission.permission_id.in_(permission_ids)
            ))
        for item in members:
            session.delete(item)
        for item in users:
            session.delete(item)
        for item in permissions:
            session.delete(item)
        for item in roles:
            session.delete(item)
        session.execute(delete(ProcessDefinition).where(
            ProcessDefinition.process_code.contains(suffix)
        ))
        for item in projects:
            session.delete(item)


def test_role_scope_assignment_and_assignment_idempotence():
    suffix = uuid4().hex[:8]
    username = f"scope_user_{suffix}"
    project_code = f"SCOPE_PROJECT_{suffix}"
    system_role = f"SCOPE_SYSTEM_{suffix}"
    project_role = f"SCOPE_PROJECT_ROLE_{suffix}"
    services = create_database_services()
    try:
        services.projects.create(ProjectCreate(
            project_code=project_code, project_name="范围测试项目"
        ))
        services.users.create(UserCreate(
            username=username, display_name="范围测试用户", password_hash=_hash(suffix)
        ))
        services.access_control.create_role(RoleCreate(
            role_code=system_role, role_name="系统角色", role_scope=RoleScope.SYSTEM
        ))
        services.access_control.create_role(RoleCreate(
            role_code=project_role, role_name="项目角色", role_scope=RoleScope.PROJECT
        ))
        services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )

        with pytest.raises(InvalidDataError):
            services.access_control.assign_system_role(
                username, RoleAssignmentCommand(role_code=project_role)
            )
        with pytest.raises(InvalidDataError):
            services.access_control.assign_project_role(
                project_code,
                username,
                RoleAssignmentCommand(role_code=system_role),
            )

        command = RoleAssignmentCommand(role_code=system_role)
        assert services.access_control.assign_system_role(username, command) == [system_role]
        assert services.access_control.assign_system_role(username, command) == [system_role]
        assert services.access_control.revoke_system_role(username, command) == []
        assert services.access_control.revoke_system_role(username, command) == []

        project_command = RoleAssignmentCommand(role_code=project_role)
        first = services.access_control.assign_project_role(
            project_code, username, project_command
        )
        second = services.access_control.assign_project_role(
            project_code, username, project_command
        )
        assert first.role_codes == [project_role]
        assert second.role_codes == [project_role]
        assert services.access_control.revoke_project_role(
            project_code, username, project_command
        ).role_codes == []

        services.access_control.assign_project_role(
            project_code, username, project_command
        )
        services.access_control.set_project_member_active(
            project_code, username, is_active=False
        )
        assert services.access_control.revoke_project_role(
            project_code, username, project_command
        ).role_codes == []
        reactivated = services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )
        assert reactivated.role_codes == []
        assert services.access_control.revoke_project_role(
            project_code, username, project_command
        ).role_codes == []
    finally:
        _cleanup(suffix=suffix)


def test_add_project_member_is_idempotent_and_reactivates_existing_record():
    suffix = uuid4().hex[:8]
    username = f"member_idempotent_{suffix}"
    project_code = f"MEMBER_IDEMPOTENT_{suffix}"
    services = create_database_services()
    try:
        project = services.projects.create(ProjectCreate(
            project_code=project_code, project_name="成员幂等测试项目"
        ))
        user = services.users.create(UserCreate(
            username=username, display_name="成员幂等测试用户", password_hash=_hash(suffix)
        ))

        first = services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )
        repeated = services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )

        assert repeated.id == first.id
        assert repeated.is_active is True

        with SessionLocal() as session:
            assert session.query(ProjectMember).filter_by(
                project_id=project.id, user_id=user.id
            ).count() == 1

        services.access_control.set_project_member_active(
            project_code, username, is_active=False
        )
        reactivated = services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )

        assert reactivated.id == first.id
        assert reactivated.is_active is True
        with SessionLocal() as session:
            assert session.query(ProjectMember).filter_by(
                project_id=project.id, user_id=user.id
            ).count() == 1
    finally:
        _cleanup(suffix=suffix)


def test_effective_permissions_deduplicate_and_respect_inactive_resources():
    suffix = uuid4().hex[:8]
    username = f"effective_user_{suffix}"
    project_code = f"EFFECTIVE_PROJECT_{suffix}"
    system_role = f"EFFECTIVE_SYSTEM_{suffix}"
    project_role = f"EFFECTIVE_PROJECT_ROLE_{suffix}"
    permission_code = f"effective.shared.{suffix}"
    services = create_database_services()
    try:
        services.projects.create(ProjectCreate(
            project_code=project_code, project_name="有效权限测试项目"
        ))
        user = services.users.create(UserCreate(
            username=username, display_name="有效权限用户", password_hash=_hash(suffix)
        ))
        services.access_control.create_role(RoleCreate(
            role_code=system_role, role_name="系统角色", role_scope=RoleScope.SYSTEM
        ))
        services.access_control.create_role(RoleCreate(
            role_code=project_role, role_name="项目角色", role_scope=RoleScope.PROJECT
        ))
        services.access_control.create_permission(PermissionCreate(
            permission_code=permission_code,
            permission_name="共享权限",
            module_code="effective",
        ))
        permission_command = RolePermissionCommand(permission_code=permission_code)
        services.access_control.assign_permission(system_role, permission_command)
        services.access_control.assign_permission(project_role, permission_command)
        services.access_control.assign_system_role(
            username, RoleAssignmentCommand(role_code=system_role)
        )
        services.access_control.add_project_member(
            project_code, ProjectMemberCreate(username=username)
        )
        services.access_control.assign_project_role(
            project_code, username, RoleAssignmentCommand(role_code=project_role)
        )

        def effective() -> list[str]:
            return services.access_control.get_effective_permissions(
                username, project_code=project_code
            ).permission_codes

        assert effective() == [permission_code]

        services.access_control.set_role_active(system_role, is_active=False)
        assert effective() == [permission_code]
        services.access_control.set_role_active(project_role, is_active=False)
        assert effective() == []

        services.access_control.set_role_active(system_role, is_active=True)
        services.access_control.set_role_active(project_role, is_active=True)
        services.access_control.set_permission_active(permission_code, is_active=False)
        assert effective() == []

        services.access_control.set_permission_active(permission_code, is_active=True)
        services.users.set_active(user.id, is_active=False)
        with pytest.raises(InactiveResourceError):
            effective()
    finally:
        _cleanup(suffix=suffix)


def test_user_update_activation_filter_and_real_pagination():
    suffix = uuid4().hex[:8]
    services = create_database_services()
    usernames = [f"page_user_{suffix}_{letter}" for letter in "ABC"]
    try:
        users = [services.users.create(UserCreate(
            username=username,
            display_name=f"用户{letter}",
            password_hash=_hash(f"{suffix}_{letter}"),
        )) for username, letter in zip(usernames, "ABC", strict=True)]

        updated = services.users.update(
            users[0].id, UserUpdate(display_name="更新后的用户A", remark="已更新")
        )
        assert updated.display_name == "更新后的用户A"
        assert updated.remark == "已更新"
        assert services.users.set_active(users[1].id, is_active=False).is_active is False

        first = services.users.list(
            UserFilter(keyword=f"page_user_{suffix}"),
            PageRequest(page=1, page_size=2),
            sort_by=UserSortField.USERNAME,
            sort_order=SortOrder.ASC,
        )
        second = services.users.list(
            UserFilter(keyword=f"page_user_{suffix}"),
            PageRequest(page=2, page_size=2),
            sort_by=UserSortField.USERNAME,
            sort_order=SortOrder.ASC,
        )
        assert [item.username for item in first.items] == usernames[:2]
        assert first.total == 3
        assert first.has_next is True
        assert first.has_previous is False
        assert [item.username for item in second.items] == usernames[2:]
        assert second.has_next is False
        assert second.has_previous is True

        inactive = services.users.list(
            UserFilter(keyword=f"page_user_{suffix}", is_active=False),
            PageRequest(page_size=10),
        )
        assert [item.username for item in inactive.items] == [usernames[1]]
    finally:
        _cleanup(suffix=suffix)


def test_duplicate_process_code_maps_to_public_conflict():
    suffix = uuid4().hex[:8]
    process_code = f"DUPLICATE_PROCESS_{suffix}"
    service = create_database_services().processes
    try:
        data = ProcessDefinitionCreate(
            process_code=process_code, process_name="重复工序"
        )
        service.create(data)
        with pytest.raises(ResourceAlreadyExistsError):
            service.create(data)
    finally:
        _cleanup(suffix=suffix)


def test_role_permission_and_project_member_real_pagination():
    suffix = uuid4().hex[:8]
    project_code = f"PAGE_PROJECT_{suffix}"
    role_codes = [f"PAGE_ROLE_{suffix}_{letter}" for letter in "ABC"]
    permission_codes = [f"page.permission.{suffix}.{letter}" for letter in "ABC"]
    usernames = [f"member_{suffix}_{letter}" for letter in "ABC"]
    services = create_database_services()
    try:
        services.projects.create(ProjectCreate(
            project_code=project_code, project_name="分页项目"
        ))
        for role_code, letter in zip(role_codes, "ABC", strict=True):
            services.access_control.create_role(RoleCreate(
                role_code=role_code,
                role_name=f"分页角色{letter}",
                role_scope=RoleScope.PROJECT,
            ))
        for permission_code, letter in zip(permission_codes, "ABC", strict=True):
            services.access_control.create_permission(PermissionCreate(
                permission_code=permission_code,
                permission_name=f"分页权限{letter}",
                module_code=f"page_{suffix}",
            ))
        for username, letter in zip(usernames, "ABC", strict=True):
            services.users.create(UserCreate(
                username=username,
                display_name=f"项目成员{letter}",
                password_hash=_hash(f"{suffix}_{letter}"),
            ))
            services.access_control.add_project_member(
                project_code, ProjectMemberCreate(username=username)
            )

        role_page = services.access_control.list_roles(
            RoleFilter(keyword=f"PAGE_ROLE_{suffix}"),
            PageRequest(page=2, page_size=2),
            sort_by=RoleSortField.ROLE_CODE,
            sort_order=SortOrder.ASC,
        )
        assert [item.role_code for item in role_page.items] == role_codes[2:]
        assert role_page.total == 3
        assert role_page.has_next is False
        assert role_page.has_previous is True

        permission_page = services.access_control.list_permission_catalog(
            PermissionFilter(module_code=f"page_{suffix}"),
            PageRequest(page=1, page_size=2),
            sort_by=PermissionSortField.PERMISSION_CODE,
            sort_order=SortOrder.DESC,
        )
        assert [item.permission_code for item in permission_page.items] == list(
            reversed(permission_codes)
        )[:2]
        assert permission_page.total == 3
        assert permission_page.has_next is True

        member_page = services.access_control.list_project_members(
            project_code,
            ProjectMemberFilter(keyword=f"member_{suffix}"),
            PageRequest(page=2, page_size=2),
            sort_by=ProjectMemberSortField.USERNAME,
            sort_order=SortOrder.ASC,
        )
        assert [item.username for item in member_page.items] == usernames[2:]
        assert member_page.total == 3
        assert member_page.has_next is False
        assert member_page.has_previous is True

        select_statements = []

        def record_statement(*args):
            statement = args[2]
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            batch_page = services.access_control.list_project_members(
                project_code,
                ProjectMemberFilter(keyword=f"member_{suffix}"),
                PageRequest(page=1, page_size=3),
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
        assert len(batch_page.items) == 3
        assert len(select_statements) <= 4
    finally:
        _cleanup(suffix=suffix)


def test_role_code_rejects_values_longer_than_database_column():
    with pytest.raises(ValidationError):
        RoleCreate(
            role_code="R" * 65,
            role_name="超长角色",
            role_scope=RoleScope.SYSTEM,
        )


def test_project_scoped_yard_resources_do_not_cross_project_boundaries():
    suffix = uuid4().hex[:8]
    project_a = f"AUDIT_PROJECT_A_{suffix}"
    project_b = f"AUDIT_PROJECT_B_{suffix}"
    type_a = f"AUDIT_TYPE_A_{suffix}"
    type_b = f"AUDIT_TYPE_B_{suffix}"
    global_type = f"AUDIT_TYPE_GLOBAL_{suffix}"
    area_a = f"AUDIT_AREA_A_{suffix}"
    area_b = f"AUDIT_AREA_B_{suffix}"
    position_a = f"AUDIT_POSITION_A_{suffix}"
    position_b = f"AUDIT_POSITION_B_{suffix}"
    beam_a = f"AUDIT_BEAM_A_{suffix}"
    services = create_database_services()
    try:
        services.projects.create(ProjectCreate(
            project_code=project_a, project_name="项目A"
        ))
        services.projects.create(ProjectCreate(
            project_code=project_b, project_name="项目B"
        ))
        services.beam_types.create(BeamTypeCreate(
            type_code=type_a, type_name="A梁型", project_code=project_a
        ))
        services.beam_types.create(BeamTypeCreate(
            type_code=type_b, type_name="B梁型", project_code=project_b
        ))
        services.beam_types.create(BeamTypeCreate(
            type_code=global_type, type_name="通用梁型"
        ))
        process_a = f"AUDIT_PROCESS_A_{suffix}"
        process_b = f"AUDIT_PROCESS_B_{suffix}"
        process_global = f"AUDIT_PROCESS_GLOBAL_{suffix}"
        services.processes.create(ProcessDefinitionCreate(
            process_code=process_a,
            process_name="项目A工序",
            project_code=project_a,
        ))
        services.processes.create(ProcessDefinitionCreate(
            process_code=process_b,
            process_name="项目B工序",
            project_code=project_b,
        ))
        services.processes.create(ProcessDefinitionCreate(
            process_code=process_global,
            process_name="通用工序",
        ))
        scoped_processes = services.processes.list(
            ProcessDefinitionFilter(project_code=project_a, include_global=True),
            PageRequest(page_size=10),
        )
        assert {item.process_code for item in scoped_processes.items} == {
            process_a,
            process_global,
        }
        with pytest.raises(ProcessDefinitionNotFoundError):
            services.processes.get_by_code(process_b, project_code=project_a)

        scoped_types = services.beam_types.list(
            BeamTypeFilter(project_code=project_a, include_global=True),
            PageRequest(page_size=10),
        )
        assert {item.type_code for item in scoped_types.items} == {
            type_a,
            global_type,
        }
        assert services.beam_types.get_by_code(
            type_a, project_code=project_a
        ).project_code == project_a
        with pytest.raises(BeamTypeNotFoundError):
            services.beam_types.get_by_code(type_a, project_code=project_b)
        with pytest.raises(BeamTypeNotFoundError):
            services.beam_types.get_by_code(type_a)

        services.yard_areas.create(YardAreaCreate(
            area_code=area_a,
            area_name="项目A区域",
            area_type="STORAGE",
            project_code=project_a,
        ))
        services.yard_areas.create(YardAreaCreate(
            area_code=area_b,
            area_name="项目B区域",
            area_type="STORAGE",
            project_code=project_b,
        ))
        services.beam_positions.create(BeamPositionCreate(
            position_code=position_a,
            area_code=area_a,
            project_code=project_a,
        ))
        services.beam_positions.create(BeamPositionCreate(
            position_code=position_b,
            area_code=area_b,
            project_code=project_b,
        ))
        with pytest.raises(YardAreaNotFoundError):
            services.beam_positions.create(BeamPositionCreate(
                position_code=f"AUDIT_WRONG_POSITION_{suffix}",
                area_code=area_b,
                project_code=project_a,
            ))

        services.beams.create(BeamCreate(
            beam_code=beam_a,
            beam_type_code=type_a,
            project_code=project_a,
        ))
        with pytest.raises(BeamTypeNotFoundError):
            services.beams.create(BeamCreate(
                beam_code=f"AUDIT_WRONG_BEAM_{suffix}",
                beam_type_code=type_b,
                project_code=project_a,
            ))
        with pytest.raises(BeamPositionNotFoundError):
            services.beams.assign_position(
                beam_a,
                BeamPositionCommand(position_code=position_b),
                project_code=project_a,
            )
        with pytest.raises(BeamNotFoundError):
            services.beams.get_by_code(beam_a, project_code=project_b)
    finally:
        _cleanup(suffix=suffix)
