from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from backend_db.database.mysql import SessionLocal
from backend_db.exceptions import (
    BackendDBError,
    BeamTypeNotFoundError,
    DatabaseUnavailableError,
    ResourceAlreadyExistsError,
)
from backend_db.models import BeamType
from backend_db.schemas import (
    BeamTypeCreate,
    BeamTypeFilter,
    BeamTypeRead,
    BeamTypeSortField,
    BeamTypeUpdate,
    PageRequest,
    PageResult,
    SortOrder,
)
from backend_db.services import BeamTypeService


@pytest.fixture
def type_code_prefix():
    prefix = f"TEST_SERVICE_{uuid4().hex[:8]}"
    yield prefix

    with SessionLocal.begin() as session:
        session.execute(
            delete(BeamType).where(BeamType.type_code.like(f"{prefix}%"))
        )


def test_service_create_returns_dto_and_commits(type_code_prefix):
    service = BeamTypeService()

    result = service.create(
        BeamTypeCreate(
            type_code=type_code_prefix,
            type_name="Service创建测试梁型",
        )
    )

    assert isinstance(result, BeamTypeRead)
    assert not isinstance(result, BeamType)
    assert result.id > 0
    assert service.get(result.id).type_code == type_code_prefix
    assert service.get_by_code(type_code_prefix).id == result.id


def test_service_converts_duplicate_code_to_public_exception(type_code_prefix):
    service = BeamTypeService()
    data = BeamTypeCreate(
        type_code=type_code_prefix,
        type_name="重复编码测试梁型",
    )
    service.create(data)

    with pytest.raises(ResourceAlreadyExistsError) as captured:
        service.create(data)

    assert captured.value.code == "resource_already_exists"
    assert captured.value.__cause__ is None


def test_service_converts_missing_records_to_public_exception():
    service = BeamTypeService()

    with pytest.raises(BeamTypeNotFoundError):
        service.get(9_000_000_000)

    with pytest.raises(BeamTypeNotFoundError):
        service.get_by_code(f"MISSING_{uuid4().hex[:8]}")


def test_service_updates_only_submitted_fields(type_code_prefix):
    service = BeamTypeService()
    created = service.create(
        BeamTypeCreate(
            type_code=type_code_prefix,
            type_name="更新前",
            description="保留描述",
        )
    )

    updated = service.update(
        created.id,
        BeamTypeUpdate(type_name="更新后"),
    )

    assert updated.type_name == "更新后"
    assert updated.description == "保留描述"
    assert service.get(created.id).type_name == "更新后"


def test_service_set_active_uses_dedicated_operation(type_code_prefix):
    service = BeamTypeService()
    created = service.create(
        BeamTypeCreate(
            type_code=type_code_prefix,
            type_name="启停测试梁型",
        )
    )

    updated = service.set_active(created.id, is_active=False)

    assert updated.is_active is False
    assert service.get(created.id).is_active is False


def test_service_list_returns_typed_page_with_total(type_code_prefix):
    service = BeamTypeService()

    for suffix in ("C", "A", "B"):
        service.create(
            BeamTypeCreate(
                type_code=f"{type_code_prefix}_{suffix}",
                type_name=f"列表测试{suffix}",
            )
        )

    result = service.list(
        BeamTypeFilter(keyword=type_code_prefix),
        PageRequest(page=1, page_size=2),
        sort_by=BeamTypeSortField.TYPE_CODE,
        sort_order=SortOrder.ASC,
    )

    assert isinstance(result, PageResult)
    assert [item.type_code for item in result.items] == [
        f"{type_code_prefix}_A",
        f"{type_code_prefix}_B",
    ]
    assert all(not isinstance(item, BeamType) for item in result.items)
    assert result.total == 3
    assert result.has_next is True
    assert result.has_previous is False


def test_service_list_detects_next_page_without_count(type_code_prefix):
    service = BeamTypeService()

    for suffix in ("A", "B", "C"):
        service.create(
            BeamTypeCreate(
                type_code=f"{type_code_prefix}_{suffix}",
                type_name=f"免统计测试{suffix}",
            )
        )

    result = service.list(
        BeamTypeFilter(keyword=type_code_prefix),
        PageRequest(page=1, page_size=2, include_total=False),
        sort_by=BeamTypeSortField.TYPE_CODE,
    )

    assert len(result.items) == 2
    assert result.total is None
    assert result.has_next is True


def test_service_hides_unexpected_sqlalchemy_errors(monkeypatch):
    def raise_database_error(*args, **kwargs):
        raise SQLAlchemyError("底层数据库错误")

    monkeypatch.setattr(
        "backend_db.services.beam_type.get_beam_type",
        raise_database_error,
    )

    with pytest.raises(BackendDBError) as captured:
        BeamTypeService().get(1)

    assert type(captured.value) is BackendDBError
    assert str(captured.value) == "数据库操作失败"
    assert captured.value.__cause__ is None


def test_service_converts_operational_error_to_unavailable(monkeypatch):
    def raise_operational_error(*args, **kwargs):
        raise OperationalError(
            "SELECT 1",
            {},
            RuntimeError("数据库离线"),
        )

    monkeypatch.setattr(
        "backend_db.services.beam_type.get_beam_type",
        raise_operational_error,
    )

    with pytest.raises(DatabaseUnavailableError) as captured:
        BeamTypeService().get(1)

    assert captured.value.code == "database_unavailable"
    assert captured.value.__cause__ is None
