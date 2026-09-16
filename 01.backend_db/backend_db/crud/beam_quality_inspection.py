from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend_db.models import (
    Beam,
    BeamProcessExecution,
    BeamQualityInspection,
    BeamQualityInspectionItem,
    ProcessDefinition,
)


SORT_COLUMNS = {
    "id": BeamQualityInspection.id,
    "inspection_code": BeamQualityInspection.inspection_code,
    "inspection_type_code": BeamQualityInspection.inspection_type_code,
    "result_code": BeamQualityInspection.result_code,
    "inspected_at": BeamQualityInspection.inspected_at,
    "created_at": BeamQualityInspection.created_at,
}
VOID_FIELDS = frozenset(
    {
        "is_voided",
        "voided_at",
        "voided_by_user_id",
        "voided_by_name",
        "void_reason",
    }
)


def _statement(*, include_items: bool = True):
    options = [
        joinedload(BeamQualityInspection.project),
        joinedload(BeamQualityInspection.beam),
        joinedload(BeamQualityInspection.process_definition),
        joinedload(BeamQualityInspection.process_execution),
        joinedload(BeamQualityInspection.previous_inspection),
    ]
    if include_items:
        options.append(selectinload(BeamQualityInspection.items))
    return select(BeamQualityInspection).options(*options)


def create_beam_quality_inspection(
    session: Session,
    values: Mapping[str, object],
    item_values: Sequence[Mapping[str, object]],
) -> BeamQualityInspection:
    inspection = BeamQualityInspection(**values)
    session.add(inspection)
    session.flush()
    session.add_all(
        BeamQualityInspectionItem(inspection_id=inspection.id, **item)
        for item in item_values
    )
    session.flush()
    session.refresh(inspection, attribute_names=["items"])
    return inspection


def has_beam_quality_inspection_for_process(
    session: Session,
    process_definition_id: int,
) -> bool:
    return session.scalar(
        select(BeamQualityInspection.id)
        .where(
            BeamQualityInspection.process_definition_id
            == process_definition_id
        )
        .limit(1)
    ) is not None


def get_beam_quality_inspection_by_code(
    session: Session,
    inspection_code: str,
    *,
    for_update: bool = False,
) -> BeamQualityInspection | None:
    query = _statement().where(
        BeamQualityInspection.inspection_code == inspection_code
    )
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_beam_quality_inspection_by_external_key(
    session: Session,
    source: str,
    external_record_id: str,
) -> BeamQualityInspection | None:
    return session.scalar(
        _statement().where(
            BeamQualityInspection.source == source,
            BeamQualityInspection.external_record_id == external_record_id,
        )
    )


def set_beam_quality_inspection_voided(
    session: Session,
    item: BeamQualityInspection,
    changes: Mapping[str, object],
) -> BeamQualityInspection:
    unsupported = set(changes) - VOID_FIELDS
    if unsupported:
        raise ValueError(
            f"不允许更新质量检查记录字段: {', '.join(sorted(unsupported))}"
        )
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def list_beam_quality_inspections(
    session: Session,
    *,
    project_id: int | None = None,
    inspection_code: str | None = None,
    beam_code: str | None = None,
    process_code: str | None = None,
    process_execution_code: str | None = None,
    inspection_type_code: str | None = None,
    result_codes: list[str] | None = None,
    sources: list[str] | None = None,
    inspected_at_from: datetime | None = None,
    inspected_at_to: datetime | None = None,
    is_reinspection: bool | None = None,
    is_voided: bool | None = None,
    actor_user_id: int | None = None,
    external_record_id: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "inspected_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[BeamQualityInspection], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("质量检查记录分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("质量检查记录排序参数无效")

    conditions = [
        BeamQualityInspection.project_id.is_(None)
        if project_id is None
        else BeamQualityInspection.project_id == project_id
    ]
    if inspection_code is not None:
        conditions.append(BeamQualityInspection.inspection_code == inspection_code)
    if beam_code is not None:
        conditions.append(Beam.beam_code == beam_code)
    if process_code is not None:
        conditions.append(ProcessDefinition.process_code == process_code)
    if process_execution_code is not None:
        conditions.append(
            BeamProcessExecution.execution_code == process_execution_code
        )
    if inspection_type_code is not None:
        conditions.append(
            BeamQualityInspection.inspection_type_code == inspection_type_code
        )
    if result_codes is not None:
        conditions.append(
            BeamQualityInspection.result_code.in_(result_codes)
            if result_codes
            else false()
        )
    if sources is not None:
        conditions.append(
            BeamQualityInspection.source.in_(sources) if sources else false()
        )
    if inspected_at_from is not None:
        conditions.append(BeamQualityInspection.inspected_at >= inspected_at_from)
    if inspected_at_to is not None:
        conditions.append(BeamQualityInspection.inspected_at <= inspected_at_to)
    if is_reinspection is True:
        conditions.append(BeamQualityInspection.previous_inspection_id.is_not(None))
    elif is_reinspection is False:
        conditions.append(BeamQualityInspection.previous_inspection_id.is_(None))
    if is_voided is not None:
        conditions.append(BeamQualityInspection.is_voided == is_voided)
    if actor_user_id is not None:
        conditions.append(BeamQualityInspection.actor_user_id == actor_user_id)
    if external_record_id is not None:
        conditions.append(
            BeamQualityInspection.external_record_id == external_record_id
        )
    if keyword is not None:
        conditions.append(
            or_(
                BeamQualityInspection.inspection_code.contains(
                    keyword, autoescape=True
                ),
                Beam.beam_code.contains(keyword, autoescape=True),
                BeamQualityInspection.actor_name.contains(keyword, autoescape=True),
                BeamQualityInspection.summary.contains(keyword, autoescape=True),
            )
        )

    def joins(statement):
        return (
            statement.join(Beam, Beam.id == BeamQualityInspection.beam_id)
            .outerjoin(
                ProcessDefinition,
                ProcessDefinition.id
                == BeamQualityInspection.process_definition_id,
            )
            .outerjoin(
                BeamProcessExecution,
                BeamProcessExecution.id
                == BeamQualityInspection.process_execution_id,
            )
        )

    base = joins(_statement(include_items=False)).where(*conditions)
    total = (
        session.scalar(
            joins(select(func.count()).select_from(BeamQualityInspection)).where(
                *conditions
            )
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(BeamQualityInspection.id))
    limit = page_size if include_total else page_size + 1
    items = list(
        session.scalars(
            base.order_by(*order)
            .offset((page - 1) * page_size)
            .limit(limit)
        ).unique()
    )
    has_next = len(items) > page_size if total is None else page * page_size < total
    return items[:page_size], total, has_next
