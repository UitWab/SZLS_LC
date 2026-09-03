import pytest
from pydantic import ValidationError

from backend_db.schemas import (
    PageRequest,
    PageResult,
    SchemaModel,
    SortOrder,
)


class ExampleItem(SchemaModel):
    code: str


def test_schema_model_strips_strings_and_rejects_extra_fields():
    item = ExampleItem(code="  BEAM_001  ")

    assert item.code == "BEAM_001"

    with pytest.raises(ValidationError):
        ExampleItem(code="BEAM_001", unexpected=True)


def test_page_request_defaults_and_offset():
    request = PageRequest()

    assert request.page == 1
    assert request.page_size == 20
    assert request.include_total is True
    assert request.offset == 0

    assert PageRequest(page=3, page_size=25).offset == 50


@pytest.mark.parametrize(
    "values",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_page_request_rejects_out_of_range_values(values):
    with pytest.raises(ValidationError):
        PageRequest(**values)


def test_page_result_serializes_typed_items_without_internal_objects():
    result = PageResult[ExampleItem](
        items=[ExampleItem(code="BEAM_001")],
        page=2,
        page_size=20,
        total=35,
        has_next=False,
        has_previous=True,
    )

    assert result.model_dump(mode="json") == {
        "items": [{"code": "BEAM_001"}],
        "page": 2,
        "page_size": 20,
        "total": 35,
        "has_next": False,
        "has_previous": True,
    }


def test_sort_order_uses_stable_lowercase_values():
    assert SortOrder.ASC.value == "asc"
    assert SortOrder.DESC.value == "desc"
