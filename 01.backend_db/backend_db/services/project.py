from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.project import (
    create_project,
    get_project,
    get_project_by_code,
    list_projects,
    set_project_active,
    update_project,
)
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import ProjectNotFoundError, ResourceAlreadyExistsError
from backend_db.schemas import (
    PageRequest,
    PageResult,
    ProjectCreate,
    ProjectFilter,
    ProjectRead,
    ProjectSortField,
    ProjectSummary,
    ProjectUpdate,
    SortOrder,
)
from backend_db.services._errors import raise_database_error


class ProjectService:
    """项目档案用例入口；不包含登录鉴权或项目访问授权。"""

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: ProjectCreate) -> ProjectRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = create_project(unit.session, **data.model_dump())
                result = ProjectRead.model_validate(project)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"项目编码已存在: {data.project_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, project_id: int) -> ProjectRead:
        return self._get_one(project_id=project_id)

    def get_by_code(self, project_code: str) -> ProjectRead:
        return self._get_one(project_code=project_code)

    def _get_one(
        self,
        *,
        project_id: int | None = None,
        project_code: str | None = None,
    ) -> ProjectRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = (
                    get_project(unit.session, project_id)
                    if project_id is not None
                    else get_project_by_code(unit.session, project_code or "")
                )
                if project is None:
                    identity = (
                        f"id={project_id}"
                        if project_id is not None
                        else f"project_code={project_code}"
                    )
                    raise ProjectNotFoundError(f"项目不存在: {identity}")
                return ProjectRead.model_validate(project)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: ProjectFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: ProjectSortField = ProjectSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[ProjectSummary]:
        filters = filters or ProjectFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_projects(
                    unit.session,
                    **filters.model_dump(exclude_none=True),
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[ProjectSummary](
                    items=[ProjectSummary.model_validate(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update(self, project_id: int, data: ProjectUpdate) -> ProjectRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project(unit.session, project_id)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: id={project_id}")
                changes = data.model_dump(exclude_unset=True)
                if changes:
                    update_project(unit.session, project, changes)
                result = ProjectRead.model_validate(project)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(self, project_id: int, *, is_active: bool) -> ProjectRead:
        try:
            with self._unit_of_work_factory() as unit:
                project = get_project(unit.session, project_id)
                if project is None:
                    raise ProjectNotFoundError(f"项目不存在: id={project_id}")
                set_project_active(unit.session, project, is_active=is_active)
                result = ProjectRead.model_validate(project)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)
