from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend_db.crud.yard_area import (
    create_yard_area,
    get_yard_area,
    get_yard_area_by_code,
    has_active_child_areas,
    has_active_positions,
    list_all_yard_areas,
    list_yard_areas,
    set_yard_area_active,
    update_yard_area,
)
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.exceptions import (
    InactiveResourceError,
    InvalidAreaHierarchyError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    YardAreaNotFoundError,
)
from backend_db.mappers import yard_area_to_read, yard_area_to_summary
from backend_db.schemas import (
    PageRequest,
    PageResult,
    SortOrder,
    YardAreaCreate,
    YardAreaFilter,
    YardAreaRead,
    YardAreaSortField,
    YardAreaSummary,
    YardAreaTreeNode,
    YardAreaUpdate,
)
from backend_db.services._errors import raise_database_error


class YardAreaService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork] = UnitOfWork):
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, data: YardAreaCreate) -> YardAreaRead:
        try:
            with self._unit_of_work_factory() as unit:
                parent = self._resolve_parent(unit, data.parent_area_code)
                values = data.model_dump(exclude={"parent_area_code"})
                area = create_yard_area(
                    unit.session,
                    **values,
                    parent_id=parent.id if parent else None,
                )
                result = yard_area_to_read(area)
                unit.commit()
                return result
        except IntegrityError:
            raise ResourceAlreadyExistsError(
                f"区域编码已存在: {data.area_code}"
            ) from None
        except SQLAlchemyError as error:
            raise_database_error(error)

    def get(self, area_id: int) -> YardAreaRead:
        return self._get_one(area_id=area_id)

    def get_by_code(self, area_code: str) -> YardAreaRead:
        return self._get_one(area_code=area_code)

    def _get_one(
        self,
        *,
        area_id: int | None = None,
        area_code: str | None = None,
    ) -> YardAreaRead:
        try:
            with self._unit_of_work_factory() as unit:
                area = (
                    get_yard_area(unit.session, area_id)
                    if area_id is not None
                    else get_yard_area_by_code(unit.session, area_code or "")
                )
                if area is None:
                    identity = f"id={area_id}" if area_id is not None else f"area_code={area_code}"
                    raise YardAreaNotFoundError(f"区域不存在: {identity}")
                return yard_area_to_read(area)
        except SQLAlchemyError as error:
            raise_database_error(error)

    def list(
        self,
        filters: YardAreaFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: YardAreaSortField = YardAreaSortField.SORT_ORDER,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[YardAreaSummary]:
        filters = filters or YardAreaFilter()
        page_request = page_request or PageRequest()
        try:
            with self._unit_of_work_factory() as unit:
                items, total, has_next = list_yard_areas(
                    unit.session,
                    **filters.model_dump(exclude_none=True),
                    page=page_request.page,
                    page_size=page_request.page_size,
                    sort_by=sort_by.value,
                    sort_order=sort_order.value,
                    include_total=page_request.include_total,
                )
                return PageResult[YardAreaSummary](
                    items=[yard_area_to_summary(item) for item in items],
                    page=page_request.page,
                    page_size=page_request.page_size,
                    total=total,
                    has_next=has_next,
                    has_previous=page_request.page > 1,
                )
        except SQLAlchemyError as error:
            raise_database_error(error)

    def tree(self, *, is_active: bool | None = True) -> list[YardAreaTreeNode]:
        try:
            with self._unit_of_work_factory() as unit:
                areas = list_all_yard_areas(unit.session, is_active=is_active)
                nodes = {
                    area.id: YardAreaTreeNode(
                        **yard_area_to_read(area).model_dump(),
                        children=[],
                    )
                    for area in areas
                }
                roots = []
                for area in areas:
                    node = nodes[area.id]
                    if area.parent_id in nodes:
                        nodes[area.parent_id].children.append(node)
                    else:
                        roots.append(node)
                return roots
        except SQLAlchemyError as error:
            raise_database_error(error)

    def update(self, area_id: int, data: YardAreaUpdate) -> YardAreaRead:
        try:
            with self._unit_of_work_factory() as unit:
                area = get_yard_area(unit.session, area_id, for_update=True)
                if area is None:
                    raise YardAreaNotFoundError(f"区域不存在: id={area_id}")
                changes = data.model_dump(
                    exclude_unset=True,
                    exclude={"parent_area_code"},
                )
                if "parent_area_code" in data.model_fields_set:
                    parent = self._resolve_parent(
                        unit,
                        data.parent_area_code,
                        child_id=area.id,
                    )
                    changes["parent_id"] = parent.id if parent else None
                if changes:
                    update_yard_area(unit.session, area, changes)
                    if "parent_id" in changes:
                        unit.session.expire(area, ["parent"])
                result = yard_area_to_read(area)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    def set_active(self, area_id: int, *, is_active: bool) -> YardAreaRead:
        try:
            with self._unit_of_work_factory() as unit:
                area = get_yard_area(unit.session, area_id, for_update=True)
                if area is None:
                    raise YardAreaNotFoundError(f"区域不存在: id={area_id}")
                if not is_active:
                    if has_active_child_areas(unit.session, area.id):
                        raise ResourceConflictError("区域仍有启用的子区域，不能停用")
                    if has_active_positions(unit.session, area.id):
                        raise ResourceConflictError("区域仍有启用的梁位，不能停用")
                elif area.parent is not None and not area.parent.is_active:
                    raise InactiveResourceError("父区域未启用，不能启用当前区域")
                set_yard_area_active(unit.session, area, is_active=is_active)
                result = yard_area_to_read(area)
                unit.commit()
                return result
        except SQLAlchemyError as error:
            raise_database_error(error)

    @staticmethod
    def _resolve_parent(
        unit: UnitOfWork,
        parent_area_code: str | None,
        *,
        child_id: int | None = None,
    ):
        if parent_area_code is None:
            return None
        parent = get_yard_area_by_code(
            unit.session,
            parent_area_code,
            for_update=True,
        )
        if parent is None:
            raise YardAreaNotFoundError(
                f"父区域不存在: area_code={parent_area_code}"
            )
        if not parent.is_active:
            raise InactiveResourceError("父区域未启用")
        current = parent
        visited = set()
        while current is not None and current.id not in visited:
            if child_id is not None and current.id == child_id:
                raise InvalidAreaHierarchyError("区域不能成为自身或后代的子区域")
            visited.add(current.id)
            current = (
                get_yard_area(unit.session, current.parent_id, for_update=True)
                if current.parent_id is not None
                else None
            )
        return parent
