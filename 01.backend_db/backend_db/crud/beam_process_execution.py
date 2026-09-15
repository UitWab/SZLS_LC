from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from backend_db.models import Beam, BeamProcessExecution, ProcessDefinition


SORT_COLUMNS = {
    "id": BeamProcessExecution.id,
    "execution_code": BeamProcessExecution.execution_code,
    "result_code": BeamProcessExecution.result_code,
    "started_at": BeamProcessExecution.started_at,
    "finished_at": BeamProcessExecution.finished_at,
    "created_at": BeamProcessExecution.created_at,
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


def _statement():
    return select(BeamProcessExecution).options(
        joinedload(BeamProcessExecution.project),
        joinedload(BeamProcessExecution.beam),
        joinedload(BeamProcessExecution.process_definition),
        joinedload(BeamProcessExecution.supersedes_execution),
    )


def create_beam_process_execution(
    session: Session, **values
) -> BeamProcessExecution:
    item = BeamProcessExecution(**values)
    session.add(item)
    session.flush()
    return item


def has_beam_process_execution_for_process(
    session: Session,
    process_definition_id: int,
) -> bool:
    return session.scalar(
        select(BeamProcessExecution.id)
        .where(
            BeamProcessExecution.process_definition_id
            == process_definition_id
        )
        .limit(1)
    ) is not None


def get_beam_process_execution_by_code(
    session: Session,
    execution_code: str,
    *,
    for_update: bool = False,
) -> BeamProcessExecution | None:
    query = _statement().where(
        BeamProcessExecution.execution_code == execution_code
    )
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_beam_process_execution_by_external_key(
    session: Session,
    source: str,
    external_record_id: str,
) -> BeamProcessExecution | None:
    return session.scalar(
        _statement().where(
            BeamProcessExecution.source == source,
            BeamProcessExecution.external_record_id == external_record_id,
        )
    )


def set_beam_process_execution_voided(
    session: Session,
    item: BeamProcessExecution,
    changes: Mapping[str, object],
) -> BeamProcessExecution:
    unsupported = set(changes) - VOID_FIELDS
    if unsupported:
        raise ValueError(
            f"不允许更新工序执行记录字段: {', '.join(sorted(unsupported))}"
        )
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def list_beam_process_executions(
    session: Session,
    *,
    project_id: int | None = None,
    execution_code: str | None = None,
    beam_code: str | None = None,
    process_code: str | None = None,
    result_codes: list[str] | None = None,
    sources: list[str] | None = None,
    started_at_from: datetime | None = None,
    started_at_to: datetime | None = None,
    finished_at_from: datetime | None = None,
    finished_at_to: datetime | None = None,
    is_voided: bool | None = None,
    is_correction: bool | None = None,
    actor_user_id: int | None = None,
    external_record_id: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "finished_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[BeamProcessExecution], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("工序执行记录排序参数无效")

    conditions = [
        BeamProcessExecution.project_id.is_(None)
        if project_id is None
        else BeamProcessExecution.project_id == project_id
    ]
    if execution_code is not None:
        conditions.append(BeamProcessExecution.execution_code == execution_code)
    if beam_code is not None:
        conditions.append(Beam.beam_code == beam_code)
    if process_code is not None:
        conditions.append(ProcessDefinition.process_code == process_code)
    if result_codes is not None:
        conditions.append(
            BeamProcessExecution.result_code.in_(result_codes)
            if result_codes
            else false()
        )
    if sources is not None:
        conditions.append(
            BeamProcessExecution.source.in_(sources) if sources else false()
        )
    if started_at_from is not None:
        conditions.append(BeamProcessExecution.started_at >= started_at_from)
    if started_at_to is not None:
        conditions.append(BeamProcessExecution.started_at <= started_at_to)
    if finished_at_from is not None:
        conditions.append(BeamProcessExecution.finished_at >= finished_at_from)
    if finished_at_to is not None:
        conditions.append(BeamProcessExecution.finished_at <= finished_at_to)
    if is_voided is not None:
        conditions.append(BeamProcessExecution.is_voided == is_voided)
    if is_correction is True:
        conditions.append(BeamProcessExecution.supersedes_execution_id.is_not(None))
    elif is_correction is False:
        conditions.append(BeamProcessExecution.supersedes_execution_id.is_(None))
    if actor_user_id is not None:
        conditions.append(BeamProcessExecution.actor_user_id == actor_user_id)
    if external_record_id is not None:
        conditions.append(
            BeamProcessExecution.external_record_id == external_record_id
        )
    if keyword is not None:
        conditions.append(
            or_(
                BeamProcessExecution.execution_code.contains(keyword, autoescape=True),
                Beam.beam_code.contains(keyword, autoescape=True),
                BeamProcessExecution.actor_name.contains(keyword, autoescape=True),
                BeamProcessExecution.remark.contains(keyword, autoescape=True),
            )
        )

    replacement = aliased(BeamProcessExecution)

    def joins(statement):
        return (
            statement.join(Beam, Beam.id == BeamProcessExecution.beam_id)
            .join(
                ProcessDefinition,
                ProcessDefinition.id == BeamProcessExecution.process_definition_id,
            )
            .outerjoin(
                replacement,
                replacement.id == BeamProcessExecution.supersedes_execution_id,
            )
        )

    base = joins(_statement()).where(*conditions)
    total = (
        session.scalar(
            joins(select(func.count()).select_from(BeamProcessExecution)).where(
                *conditions
            )
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(BeamProcessExecution.id))
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
