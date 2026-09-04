from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend_db.schemas import (
    BeamCreate,
    BeamFilter,
    BeamPositionCommand,
    BeamPositionCreate,
    BeamPositionFilter,
    BeamPositionRead,
    BeamPositionSortField,
    BeamPositionSummary,
    BeamPositionUpdate,
    BeamRead,
    BeamSortField,
    BeamStatusChange,
    BeamSummary,
    BeamTypeCreate,
    BeamTypeFilter,
    BeamTypeRead,
    BeamTypeSortField,
    BeamTypeSummary,
    BeamTypeUpdate,
    BeamUpdate,
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


@runtime_checkable
class BeamTypeServiceProtocol(Protocol):
    def create(self, data: BeamTypeCreate) -> BeamTypeRead: ...
    def get(self, beam_type_id: int) -> BeamTypeRead: ...
    def get_by_code(self, type_code: str) -> BeamTypeRead: ...
    def list(
        self,
        filters: BeamTypeFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamTypeSortField = BeamTypeSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamTypeSummary]: ...
    def update(self, beam_type_id: int, data: BeamTypeUpdate) -> BeamTypeRead: ...
    def set_active(self, beam_type_id: int, *, is_active: bool) -> BeamTypeRead: ...


@runtime_checkable
class YardAreaServiceProtocol(Protocol):
    def create(self, data: YardAreaCreate) -> YardAreaRead: ...
    def get(self, area_id: int) -> YardAreaRead: ...
    def get_by_code(self, area_code: str) -> YardAreaRead: ...
    def list(
        self,
        filters: YardAreaFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: YardAreaSortField = YardAreaSortField.SORT_ORDER,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[YardAreaSummary]: ...
    def tree(self, *, is_active: bool | None = True) -> list[YardAreaTreeNode]: ...
    def update(self, area_id: int, data: YardAreaUpdate) -> YardAreaRead: ...
    def set_active(self, area_id: int, *, is_active: bool) -> YardAreaRead: ...


@runtime_checkable
class BeamPositionServiceProtocol(Protocol):
    def create(self, data: BeamPositionCreate) -> BeamPositionRead: ...
    def get(self, position_id: int) -> BeamPositionRead: ...
    def get_by_code(self, position_code: str) -> BeamPositionRead: ...
    def list(
        self,
        filters: BeamPositionFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamPositionSortField = BeamPositionSortField.POSITION_CODE,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamPositionSummary]: ...
    def update(
        self,
        position_id: int,
        data: BeamPositionUpdate,
    ) -> BeamPositionRead: ...
    def set_active(self, position_id: int, *, is_active: bool) -> BeamPositionRead: ...


@runtime_checkable
class BeamServiceProtocol(Protocol):
    def create(self, data: BeamCreate) -> BeamRead: ...
    def get(self, beam_id: int) -> BeamRead: ...
    def get_by_code(self, beam_code: str) -> BeamRead: ...
    def list(
        self,
        filters: BeamFilter | None = None,
        page_request: PageRequest | None = None,
        *,
        sort_by: BeamSortField = BeamSortField.ID,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> PageResult[BeamSummary]: ...
    def update(self, beam_id: int, data: BeamUpdate) -> BeamRead: ...
    def change_status(self, beam_code: str, data: BeamStatusChange) -> BeamRead: ...
    def assign_position(
        self,
        beam_code: str,
        data: BeamPositionCommand,
    ) -> BeamRead: ...
    def move_beam(
        self,
        beam_code: str,
        data: BeamPositionCommand,
    ) -> BeamRead: ...
    def release_position(self, beam_code: str) -> BeamRead: ...


@dataclass(frozen=True)
class DatabaseServices:
    beam_types: BeamTypeServiceProtocol
    yard_areas: YardAreaServiceProtocol
    beam_positions: BeamPositionServiceProtocol
    beams: BeamServiceProtocol
