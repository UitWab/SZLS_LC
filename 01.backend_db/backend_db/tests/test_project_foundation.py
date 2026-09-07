from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from backend_db.crud.project import (
    create_project,
    get_project_by_code,
    list_projects,
    update_project,
)
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import ProjectNotFoundError, ResourceAlreadyExistsError
from backend_db.models import Project
from backend_db.schemas import (
    PageRequest,
    ProjectCreate,
    ProjectFilter,
    ProjectRead,
    ProjectSortField,
    ProjectUpdate,
)
from backend_db.services import ProjectService


def _code(prefix: str = "TEST_PROJECT") -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def test_project_schemas_normalize_and_protect_stable_code():
    data = ProjectCreate(
        project_code="  P001  ",
        project_name="  测试项目  ",
    )
    assert data.project_code == "P001"
    assert data.project_name == "测试项目"
    assert data.is_active is True

    with pytest.raises(ValidationError):
        ProjectCreate(project_code="", project_name="测试项目")
    with pytest.raises(ValidationError):
        ProjectUpdate(project_name=None)
    with pytest.raises(ValidationError):
        ProjectUpdate(project_code="P002")


def test_project_read_is_dto_not_orm():
    timestamp = datetime(2026, 9, 4, 5, 0, 0)
    model = Project(
        id=1,
        project_code="P001",
        project_name="测试项目",
        is_active=True,
        remark=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = ProjectRead.model_validate(model)
    assert isinstance(result, ProjectRead)
    assert not isinstance(result, Project)
    assert result.project_code == "P001"


def test_project_crud_flushes_without_committing():
    project_code = _code()
    with UnitOfWork() as unit:
        project = create_project(
            unit.session,
            project_code=project_code,
            project_name="CRUD项目",
        )
        assert project.id is not None
        assert get_project_by_code(unit.session, project_code) is project
        update_project(unit.session, project, {"project_name": "更新后项目"})
        assert project.project_name == "更新后项目"
        with pytest.raises(ValueError, match="project_code"):
            update_project(unit.session, project, {"project_code": "CHANGED"})

    with SessionLocal() as session:
        assert get_project_by_code(session, project_code) is None


@pytest.fixture
def project_code_prefix():
    prefix = _code("TEST_PROJECT_SERVICE")
    yield prefix
    with SessionLocal.begin() as session:
        session.execute(
            delete(Project).where(Project.project_code.like(f"{prefix}%"))
        )


def test_project_service_crud_and_public_errors(project_code_prefix):
    service = ProjectService()
    created = service.create(
        ProjectCreate(
            project_code=project_code_prefix,
            project_name="Service项目",
        )
    )
    assert isinstance(created, ProjectRead)
    assert service.get(created.id).project_code == project_code_prefix
    assert service.get_by_code(project_code_prefix).id == created.id

    updated = service.update(
        created.id,
        ProjectUpdate(project_name="更新后的项目", remark="测试备注"),
    )
    assert updated.project_name == "更新后的项目"
    assert updated.remark == "测试备注"
    assert service.set_active(created.id, is_active=False).is_active is False

    with pytest.raises(ResourceAlreadyExistsError):
        service.create(
            ProjectCreate(
                project_code=project_code_prefix,
                project_name="重复项目",
            )
        )
    with pytest.raises(ProjectNotFoundError):
        service.get(9_000_000_000)


def test_project_service_filters_pages_and_sorts(project_code_prefix):
    service = ProjectService()
    for suffix in ("C", "A", "B"):
        service.create(
            ProjectCreate(
                project_code=f"{project_code_prefix}_{suffix}",
                project_name=f"项目{suffix}",
                is_active=suffix != "B",
            )
        )

    result = service.list(
        ProjectFilter(keyword=project_code_prefix),
        PageRequest(page=1, page_size=2),
        sort_by=ProjectSortField.PROJECT_CODE,
    )
    assert [item.project_code for item in result.items] == [
        f"{project_code_prefix}_A",
        f"{project_code_prefix}_B",
    ]
    assert result.total == 3
    assert result.has_next is True

    active = service.list(
        ProjectFilter(keyword=project_code_prefix, is_active=True),
        PageRequest(page=1, page_size=100),
    )
    assert {item.project_code for item in active.items} == {
        f"{project_code_prefix}_A",
        f"{project_code_prefix}_C",
    }


@pytest.mark.parametrize(
    "query_args",
    [
        {"page": 0},
        {"page_size": 101},
        {"sort_by": "remark"},
        {"sort_order": "random"},
    ],
)
def test_project_crud_rejects_unsafe_query_arguments(query_args):
    with UnitOfWork() as unit:
        with pytest.raises(ValueError):
            list_projects(unit.session, **query_args)
