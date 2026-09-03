from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend_db.crud.beam_type import (
    create_beam_type,
    get_beam_type,
    get_beam_type_by_code,
    list_beam_types,
    set_beam_type_active,
    update_beam_type,
)
from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.models import BeamType


def _code(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def test_create_beam_type_flushes_without_committing():
    type_code = _code("TEST_CRUD_CREATE")

    with UnitOfWork() as unit_of_work:
        created = create_beam_type(
            unit_of_work.session,
            type_code=type_code,
            type_name="CRUD创建测试梁型",
        )

        assert created.id is not None
        assert get_beam_type(unit_of_work.session, created.id) is created
        assert get_beam_type_by_code(unit_of_work.session, type_code) is created

    with SessionLocal() as session:
        assert get_beam_type_by_code(session, type_code) is None


def test_get_beam_type_returns_none_when_record_does_not_exist():
    with UnitOfWork() as unit_of_work:
        assert get_beam_type(unit_of_work.session, 9_000_000_000) is None
        assert get_beam_type_by_code(
            unit_of_work.session,
            _code("NOT_FOUND"),
        ) is None


def test_list_beam_types_filters_and_paginates_with_stable_order():
    prefix = _code("TEST_CRUD_LIST")

    with UnitOfWork() as unit_of_work:
        for suffix, length_mm, is_active in (
            ("C", Decimal("32000.000"), True),
            ("A", Decimal("24000.000"), True),
            ("B", Decimal("28000.000"), False),
        ):
            create_beam_type(
                unit_of_work.session,
                type_code=f"{prefix}_{suffix}",
                type_name=f"分页测试{suffix}",
                length_mm=length_mm,
                is_active=is_active,
            )

        first_page, total, first_has_next = list_beam_types(
            unit_of_work.session,
            keyword=prefix,
            length_mm_min=Decimal("24000.000"),
            length_mm_max=Decimal("32000.000"),
            page=1,
            page_size=2,
            sort_by="type_code",
            sort_order="asc",
        )
        second_page, _, second_has_next = list_beam_types(
            unit_of_work.session,
            keyword=prefix,
            page=2,
            page_size=2,
            sort_by="type_code",
            sort_order="asc",
        )

        assert total == 3
        assert first_has_next is True
        assert [item.type_code for item in first_page] == [
            f"{prefix}_A",
            f"{prefix}_B",
        ]
        assert [item.type_code for item in second_page] == [f"{prefix}_C"]
        assert second_has_next is False


def test_list_beam_types_can_skip_total_and_filter_active_records():
    prefix = _code("TEST_CRUD_ACTIVE")

    with UnitOfWork() as unit_of_work:
        create_beam_type(
            unit_of_work.session,
            type_code=f"{prefix}_ON",
            type_name="启用梁型",
            is_active=True,
        )
        create_beam_type(
            unit_of_work.session,
            type_code=f"{prefix}_OFF",
            type_name="停用梁型",
            is_active=False,
        )

        items, total, has_next = list_beam_types(
            unit_of_work.session,
            keyword=prefix,
            is_active=True,
            include_total=False,
        )

        assert [item.type_code for item in items] == [f"{prefix}_ON"]
        assert total is None
        assert has_next is False


def test_keyword_filter_treats_sql_wildcards_as_literal_text():
    prefix = _code("TEST_CRUD_WILDCARD")

    with UnitOfWork() as unit_of_work:
        create_beam_type(
            unit_of_work.session,
            type_code=f"{prefix}_PERCENT",
            type_name="包含%字符",
        )
        create_beam_type(
            unit_of_work.session,
            type_code=f"{prefix}_PLAIN",
            type_name="普通名称",
        )

        items, total, has_next = list_beam_types(
            unit_of_work.session,
            keyword="%",
        )

        assert [item.type_code for item in items] == [f"{prefix}_PERCENT"]
        assert total == 1
        assert has_next is False


def test_update_beam_type_allows_only_explicit_update_fields():
    type_code = _code("TEST_CRUD_UPDATE")

    with UnitOfWork() as unit_of_work:
        beam_type = create_beam_type(
            unit_of_work.session,
            type_code=type_code,
            type_name="更新前",
            description="原描述",
        )

        updated = update_beam_type(
            unit_of_work.session,
            beam_type,
            {
                "type_name": "更新后",
                "description": None,
            },
        )

        assert updated is beam_type
        assert updated.type_name == "更新后"
        assert updated.description is None

        with pytest.raises(ValueError, match="type_code"):
            update_beam_type(
                unit_of_work.session,
                beam_type,
                {"type_code": "ILLEGAL_CHANGE"},
            )

        assert beam_type.type_code == type_code


def test_set_beam_type_active_updates_without_committing():
    type_code = _code("TEST_CRUD_ACTIVE_UPDATE")

    with UnitOfWork() as unit_of_work:
        beam_type = create_beam_type(
            unit_of_work.session,
            type_code=type_code,
            type_name="启停测试梁型",
        )

        result = set_beam_type_active(
            unit_of_work.session,
            beam_type,
            is_active=False,
        )

        assert result is beam_type
        assert result.is_active is False

    with SessionLocal() as session:
        persisted = session.scalar(
            select(BeamType).where(BeamType.type_code == type_code)
        )

    assert persisted is None


@pytest.mark.parametrize(
    "query_args",
    [
        {"page": 0},
        {"page_size": 101},
        {"sort_by": "description"},
        {"sort_order": "random"},
    ],
)
def test_list_beam_types_rejects_unsafe_query_arguments(query_args):
    with UnitOfWork() as unit_of_work:
        with pytest.raises(ValueError):
            list_beam_types(unit_of_work.session, **query_args)
