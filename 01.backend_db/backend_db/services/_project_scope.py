from backend_db.crud.project import get_project_by_code
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import InactiveResourceError, ProjectNotFoundError


def resolve_project_scope(
    unit: UnitOfWork,
    project_code: str | None,
    *,
    require_active: bool = False,
):
    """把公开项目编码解析为内部项目；None 表示 V1 全局数据域。"""
    if project_code is None:
        return None
    project = get_project_by_code(unit.session, project_code)
    if project is None:
        raise ProjectNotFoundError(f"项目不存在: project_code={project_code}")
    if require_active and not project.is_active:
        raise InactiveResourceError("项目未启用")
    return project


def matches_project_scope(resource_project_id: int | None, project) -> bool:
    expected_project_id = project.id if project is not None else None
    return resource_project_id == expected_project_id
