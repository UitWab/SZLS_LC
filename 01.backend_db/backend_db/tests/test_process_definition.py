from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import ProcessDefinitionNotFoundError
from backend_db.models import ProcessDefinition, Project
from backend_db.schemas import (
    PageRequest,
    ProcessDefinitionCreate,
    ProcessDefinitionFilter,
    ProcessDefinitionSortField,
    ProcessDefinitionUpdate,
    ProjectCreate,
)
from backend_db.interfaces import create_database_services


def test_process_definition_schema_protects_stable_code():
    data = ProcessDefinitionCreate(
        process_code="  CURING  ", process_name="  养护  "
    )
    assert data.process_code == "CURING"
    assert data.process_name == "养护"

    with pytest.raises(ValidationError):
        ProcessDefinitionUpdate(process_name=None)
    with pytest.raises(ValidationError):
        ProcessDefinitionUpdate(process_code="CHANGED")


def test_process_definition_service_crud_filter_and_activation():
    suffix = uuid4().hex[:8]
    project_code = f"PROCESS_PROJECT_{suffix}"
    global_code = f"GLOBAL_PROCESS_{suffix}"
    project_process_code = f"PROJECT_PROCESS_{suffix}"
    services = create_database_services()
    try:
        project = services.projects.create(ProjectCreate(
            project_code=project_code,
            project_name="工序测试项目",
        ))
        global_item = services.processes.create(ProcessDefinitionCreate(
            process_code=global_code,
            process_name="通用工序",
            sort_order=20,
        ))
        project_item = services.processes.create(ProcessDefinitionCreate(
            process_code=project_process_code,
            process_name="项目工序",
            project_code=project_code,
            sort_order=10,
        ))

        assert global_item.project_code is None
        assert project_item.project_id == project.id
        assert services.processes.get_by_code(
            project_process_code, project_code=project_code
        ).project_code == project_code

        page = services.processes.list(
            ProcessDefinitionFilter(project_code=project_code, include_global=True),
            PageRequest(page_size=10),
            sort_by=ProcessDefinitionSortField.SORT_ORDER,
        )
        assert [item.process_code for item in page.items] == [
            project_process_code,
            global_code,
        ]

        updated = services.processes.update(
            project_item.id,
            ProcessDefinitionUpdate(process_name="更新后的项目工序", project_code=None),
            project_code=project_code,
        )
        assert updated.process_name == "更新后的项目工序"
        assert updated.project_code is None
        assert services.processes.set_active(
            project_item.id, is_active=False
        ).is_active is False

        with pytest.raises(ProcessDefinitionNotFoundError):
            services.processes.get(9_000_000_000)
    finally:
        with SessionLocal.begin() as session:
            session.execute(delete(ProcessDefinition).where(
                ProcessDefinition.process_code.in_([global_code, project_process_code])
            ))
            session.execute(delete(Project).where(Project.project_code == project_code))
