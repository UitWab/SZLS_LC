from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import (
    AppUser,
    AuthPermission,
    AuthRole,
    AuthRolePermission,
    AuthUserRole,
    ProjectMember,
    ProjectMemberRole,
    UserCredential,
)
from backend_db.models.mixins import utc_now


USER_SORT_COLUMNS = {
    "id": AppUser.id,
    "username": AppUser.username,
    "display_name": AppUser.display_name,
    "created_at": AppUser.created_at,
    "updated_at": AppUser.updated_at,
}

ROLE_SORT_COLUMNS = {
    "id": AuthRole.id,
    "role_code": AuthRole.role_code,
    "role_name": AuthRole.role_name,
    "created_at": AuthRole.created_at,
    "updated_at": AuthRole.updated_at,
}

PERMISSION_SORT_COLUMNS = {
    "id": AuthPermission.id,
    "permission_code": AuthPermission.permission_code,
    "permission_name": AuthPermission.permission_name,
    "module_code": AuthPermission.module_code,
    "created_at": AuthPermission.created_at,
    "updated_at": AuthPermission.updated_at,
}

PROJECT_MEMBER_SORT_COLUMNS = {
    "id": ProjectMember.id,
    "username": AppUser.username,
    "created_at": ProjectMember.created_at,
    "updated_at": ProjectMember.updated_at,
}


def create_user_with_credential(
    session: Session,
    *,
    username: str,
    display_name: str,
    password_hash: str,
    is_active: bool = True,
    remark: str | None = None,
) -> AppUser:
    user = AppUser(
        username=username,
        display_name=display_name,
        is_active=is_active,
        remark=remark,
    )
    session.add(user)
    session.flush()
    credential = UserCredential(
        user_id=user.id,
        password_hash=password_hash,
        password_changed_at=utc_now(),
    )
    session.add(credential)
    session.flush()
    user.credential = credential
    return user


def get_user(
    session: Session,
    user_id: int,
    *,
    with_credential: bool = False,
) -> AppUser | None:
    statement = select(AppUser).where(AppUser.id == user_id)
    if with_credential:
        statement = statement.options(joinedload(AppUser.credential))
    return session.scalar(statement)


def get_user_by_username(
    session: Session,
    username: str,
    *,
    with_credential: bool = False,
) -> AppUser | None:
    statement = select(AppUser).where(AppUser.username == username)
    if with_credential:
        statement = statement.options(joinedload(AppUser.credential))
    return session.scalar(statement)


def list_users(
    session: Session,
    *,
    username: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[AppUser], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数不合法")
    if sort_by not in USER_SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("用户排序参数不合法")
    conditions = []
    if username is not None:
        conditions.append(AppUser.username == username)
    if is_active is not None:
        conditions.append(AppUser.is_active == is_active)
    if keyword is not None:
        conditions.append(or_(
            AppUser.username.contains(keyword, autoescape=True),
            AppUser.display_name.contains(keyword, autoescape=True),
        ))
    total = None
    if include_total:
        total = session.scalar(select(func.count()).select_from(AppUser).where(*conditions))
    direction = asc if sort_order == "asc" else desc
    order = [direction(USER_SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(AppUser.id))
    limit = page_size if include_total else page_size + 1
    items = list(session.scalars(
        select(AppUser).where(*conditions).order_by(*order)
        .offset((page - 1) * page_size).limit(limit)
    ).all())
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next


def update_user(session: Session, user: AppUser, changes: dict[str, object]) -> AppUser:
    if set(changes) - {"display_name", "remark"}:
        raise ValueError("包含不允许更新的用户字段")
    for name, value in changes.items():
        setattr(user, name, value)
    session.flush()
    return user


def set_user_active(session: Session, user: AppUser, *, is_active: bool) -> AppUser:
    user.is_active = is_active
    session.flush()
    return user


def set_password_hash(
    session: Session,
    credential: UserCredential,
    *,
    password_hash: str,
) -> UserCredential:
    credential.password_hash = password_hash
    credential.password_changed_at = utc_now()
    session.flush()
    return credential


def create_role(session: Session, **values) -> AuthRole:
    role = AuthRole(**values)
    session.add(role)
    session.flush()
    return role


def get_role_by_code(session: Session, role_code: str, *, for_update: bool = False):
    statement = select(AuthRole).where(AuthRole.role_code == role_code)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_roles(
    session: Session,
    *,
    role_code: str | None = None,
    role_scope: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[AuthRole], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数不合法")
    if sort_by not in ROLE_SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("角色排序参数不合法")
    conditions = []
    if role_code is not None:
        conditions.append(AuthRole.role_code == role_code)
    if role_scope is not None:
        conditions.append(AuthRole.role_scope == role_scope)
    if is_active is not None:
        conditions.append(AuthRole.is_active == is_active)
    if keyword is not None:
        conditions.append(or_(
            AuthRole.role_code.contains(keyword, autoescape=True),
            AuthRole.role_name.contains(keyword, autoescape=True),
        ))
    total = None
    if include_total:
        total = session.scalar(select(func.count()).select_from(AuthRole).where(*conditions))
    direction = asc if sort_order == "asc" else desc
    order = [direction(ROLE_SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(AuthRole.id))
    limit = page_size if include_total else page_size + 1
    items = list(session.scalars(
        select(AuthRole).where(*conditions).order_by(*order)
        .offset((page - 1) * page_size).limit(limit)
    ).all())
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next


def update_role(session: Session, role: AuthRole, changes: dict[str, object]) -> AuthRole:
    if set(changes) - {"role_name", "description"}:
        raise ValueError("包含不允许更新的角色字段")
    for name, value in changes.items():
        setattr(role, name, value)
    session.flush()
    return role


def set_role_active(session: Session, role: AuthRole, *, is_active: bool) -> AuthRole:
    role.is_active = is_active
    session.flush()
    return role


def create_permission(session: Session, **values) -> AuthPermission:
    permission = AuthPermission(**values)
    session.add(permission)
    session.flush()
    return permission


def get_permission_by_code(session: Session, permission_code: str):
    return session.scalar(select(AuthPermission).where(
        AuthPermission.permission_code == permission_code
    ))


def list_permissions(
    session: Session,
    *,
    permission_code: str | None = None,
    module_code: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[AuthPermission], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数不合法")
    if sort_by not in PERMISSION_SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("权限排序参数不合法")
    conditions = []
    if permission_code is not None:
        conditions.append(AuthPermission.permission_code == permission_code)
    if module_code is not None:
        conditions.append(AuthPermission.module_code == module_code)
    if is_active is not None:
        conditions.append(AuthPermission.is_active == is_active)
    if keyword is not None:
        conditions.append(or_(
            AuthPermission.permission_code.contains(keyword, autoescape=True),
            AuthPermission.permission_name.contains(keyword, autoescape=True),
        ))
    total = None
    if include_total:
        total = session.scalar(
            select(func.count()).select_from(AuthPermission).where(*conditions)
        )
    direction = asc if sort_order == "asc" else desc
    order = [direction(PERMISSION_SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(AuthPermission.id))
    limit = page_size if include_total else page_size + 1
    items = list(session.scalars(
        select(AuthPermission).where(*conditions).order_by(*order)
        .offset((page - 1) * page_size).limit(limit)
    ).all())
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next


def update_permission(
    session: Session,
    permission: AuthPermission,
    changes: dict[str, object],
) -> AuthPermission:
    if set(changes) - {"permission_name", "module_code", "description"}:
        raise ValueError("包含不允许更新的权限字段")
    for name, value in changes.items():
        setattr(permission, name, value)
    session.flush()
    return permission


def set_permission_active(
    session: Session,
    permission: AuthPermission,
    *,
    is_active: bool,
) -> AuthPermission:
    permission.is_active = is_active
    session.flush()
    return permission


def assign_role_permission(
    session: Session,
    role: AuthRole,
    permission: AuthPermission,
) -> None:
    existing = session.get(AuthRolePermission, (role.id, permission.id))
    if existing is None:
        session.add(AuthRolePermission(role_id=role.id, permission_id=permission.id))
        session.flush()


def revoke_role_permission(
    session: Session,
    role: AuthRole,
    permission: AuthPermission,
) -> None:
    existing = session.get(AuthRolePermission, (role.id, permission.id))
    if existing is not None:
        session.delete(existing)
        session.flush()


def list_role_permissions(session: Session, role_id: int) -> list[AuthPermission]:
    return list(session.scalars(
        select(AuthPermission)
        .join(AuthRolePermission)
        .where(AuthRolePermission.role_id == role_id)
        .order_by(AuthPermission.permission_code.asc())
    ).all())


def assign_system_role(session: Session, user: AppUser, role: AuthRole) -> None:
    if session.get(AuthUserRole, (user.id, role.id)) is None:
        session.add(AuthUserRole(user_id=user.id, role_id=role.id))
        session.flush()


def revoke_system_role(session: Session, user: AppUser, role: AuthRole) -> None:
    existing = session.get(AuthUserRole, (user.id, role.id))
    if existing is not None:
        session.delete(existing)
        session.flush()


def list_user_role_codes(session: Session, user_id: int) -> list[str]:
    return list(session.scalars(
        select(AuthRole.role_code)
        .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
        .where(AuthUserRole.user_id == user_id)
        .order_by(AuthRole.role_code)
    ).all())


def get_project_member(session: Session, project_id: int, user_id: int):
    return session.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ))


def create_project_member(session: Session, project_id: int, user_id: int):
    member = ProjectMember(project_id=project_id, user_id=user_id, is_active=True)
    session.add(member)
    session.flush()
    return member


def list_project_members(
    session: Session,
    project_id: int,
    *,
    username: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    include_total: bool = True,
) -> tuple[list[tuple[ProjectMember, str]], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数不合法")
    if sort_by not in PROJECT_MEMBER_SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("项目成员排序参数不合法")
    conditions = [ProjectMember.project_id == project_id]
    if username is not None:
        conditions.append(AppUser.username == username)
    if is_active is not None:
        conditions.append(ProjectMember.is_active == is_active)
    if keyword is not None:
        conditions.append(or_(
            AppUser.username.contains(keyword, autoescape=True),
            AppUser.display_name.contains(keyword, autoescape=True),
        ))
    base = select(ProjectMember, AppUser.username).join(
        AppUser, AppUser.id == ProjectMember.user_id
    ).where(*conditions)
    total = None
    if include_total:
        total = session.scalar(
            select(func.count()).select_from(ProjectMember)
            .join(AppUser, AppUser.id == ProjectMember.user_id)
            .where(*conditions)
        )
    direction = asc if sort_order == "asc" else desc
    order = [direction(PROJECT_MEMBER_SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(ProjectMember.id))
    limit = page_size if include_total else page_size + 1
    rows = list(session.execute(
        base.order_by(*order).offset((page - 1) * page_size).limit(limit)
    ).all())
    has_next = len(rows) > page_size if total is None else page * page_size < total
    return [(row[0], row[1]) for row in rows[:page_size]], total, has_next


def set_project_member_active(
    session: Session,
    member: ProjectMember,
    *,
    is_active: bool,
) -> ProjectMember:
    member.is_active = is_active
    session.flush()
    return member


def assign_project_role(session: Session, member: ProjectMember, role: AuthRole) -> None:
    if session.get(ProjectMemberRole, (member.id, role.id)) is None:
        session.add(ProjectMemberRole(project_member_id=member.id, role_id=role.id))
        session.flush()


def revoke_project_role(session: Session, member: ProjectMember, role: AuthRole) -> None:
    existing = session.get(ProjectMemberRole, (member.id, role.id))
    if existing is not None:
        session.delete(existing)
        session.flush()


def list_member_role_codes(session: Session, member_id: int) -> list[str]:
    return list(session.scalars(
        select(AuthRole.role_code).join(ProjectMemberRole).where(
            ProjectMemberRole.project_member_id == member_id
        ).order_by(AuthRole.role_code)
    ).all())


def list_member_role_codes_by_member_ids(
    session: Session,
    member_ids: list[int],
) -> dict[int, list[str]]:
    """批量读取成员角色，避免成员分页结果产生 N+1 查询。"""
    result = {member_id: [] for member_id in member_ids}
    if not member_ids:
        return result
    rows = session.execute(
        select(ProjectMemberRole.project_member_id, AuthRole.role_code)
        .join(AuthRole, AuthRole.id == ProjectMemberRole.role_id)
        .where(ProjectMemberRole.project_member_id.in_(member_ids))
        .order_by(ProjectMemberRole.project_member_id, AuthRole.role_code)
    ).all()
    for member_id, role_code in rows:
        result[member_id].append(role_code)
    return result


def list_effective_permission_codes(
    session: Session,
    user_id: int,
    project_member_id: int | None,
) -> list[str]:
    system_codes = session.scalars(
        select(AuthPermission.permission_code)
        .join(AuthRolePermission)
        .join(AuthRole, AuthRole.id == AuthRolePermission.role_id)
        .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
        .where(
            AuthUserRole.user_id == user_id,
            AuthRole.role_scope == "SYSTEM",
            AuthRole.is_active.is_(True),
            AuthPermission.is_active.is_(True),
        )
    ).all()
    codes = set(system_codes)
    if project_member_id is not None:
        codes.update(session.scalars(
            select(AuthPermission.permission_code)
            .join(AuthRolePermission)
            .join(AuthRole, AuthRole.id == AuthRolePermission.role_id)
            .join(ProjectMemberRole, ProjectMemberRole.role_id == AuthRole.id)
            .where(
                ProjectMemberRole.project_member_id == project_member_id,
                AuthRole.role_scope == "PROJECT",
                AuthRole.is_active.is_(True),
                AuthPermission.is_active.is_(True),
            )
        ).all())
    return sorted(codes)
