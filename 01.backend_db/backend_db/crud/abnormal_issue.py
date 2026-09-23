from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend_db.models import AbnormalIssue, Beam


STATE_UPDATE_FIELDS = frozenset(
    {
        "status",
        "processing_started_at",
        "processing_by_user_id",
        "processing_by_name",
        "resolved_at",
        "resolved_by_user_id",
        "resolved_by_name",
        "resolution_summary",
        "closed_at",
        "closed_by_user_id",
        "closed_by_name",
        "close_note",
    }
)
SORT_COLUMNS = {
    "id": AbnormalIssue.id,
    "issue_code": AbnormalIssue.issue_code,
    "category_code": AbnormalIssue.category_code,
    "severity": AbnormalIssue.severity,
    "status": AbnormalIssue.status,
    "occurred_at": AbnormalIssue.occurred_at,
    "created_at": AbnormalIssue.created_at,
    "updated_at": AbnormalIssue.updated_at,
}


def _statement():
    return select(AbnormalIssue).options(
        joinedload(AbnormalIssue.project),
        joinedload(AbnormalIssue.beam),
    )


def create_abnormal_issue(session: Session, **values) -> AbnormalIssue:
    item = AbnormalIssue(**values)
    session.add(item)
    session.flush()
    return item


def get_abnormal_issue_by_code(
    session: Session,
    issue_code: str,
    *,
    for_update: bool = False,
) -> AbnormalIssue | None:
    query = _statement().where(AbnormalIssue.issue_code == issue_code)
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def get_abnormal_issue_by_external_key(
    session: Session,
    source: str,
    external_record_id: str,
) -> AbnormalIssue | None:
    return session.scalar(
        _statement().where(
            AbnormalIssue.source == source,
            AbnormalIssue.external_record_id == external_record_id,
        )
    )


def set_abnormal_issue_state(
    session: Session,
    item: AbnormalIssue,
    changes: Mapping[str, object],
) -> AbnormalIssue:
    unsupported = set(changes) - STATE_UPDATE_FIELDS
    if unsupported:
        raise ValueError(f"不允许更新异常事项字段: {', '.join(sorted(unsupported))}")
    for name, value in changes.items():
        setattr(item, name, value)
    session.flush()
    return item


def list_abnormal_issues(
    session: Session,
    *,
    project_id: int,
    issue_code: str | None = None,
    beam_code: str | None = None,
    device_code: str | None = None,
    category_codes: list[str] | None = None,
    issue_type_codes: list[str] | None = None,
    severities: list[str] | None = None,
    statuses: list[str] | None = None,
    sources: list[str] | None = None,
    occurred_at_from: datetime | None = None,
    occurred_at_to: datetime | None = None,
    external_record_id: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    include_total: bool = True,
) -> tuple[list[AbnormalIssue], int | None, bool]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("分页参数超出允许范围")
    if sort_by not in SORT_COLUMNS or sort_order not in {"asc", "desc"}:
        raise ValueError("异常事项排序参数无效")

    conditions = [AbnormalIssue.project_id == project_id]
    if issue_code:
        conditions.append(AbnormalIssue.issue_code == issue_code)
    if beam_code:
        conditions.append(Beam.beam_code == beam_code)
    if device_code:
        conditions.append(AbnormalIssue.device_code == device_code)
    for values, column in (
        (category_codes, AbnormalIssue.category_code),
        (issue_type_codes, AbnormalIssue.issue_type_code),
        (severities, AbnormalIssue.severity),
        (statuses, AbnormalIssue.status),
        (sources, AbnormalIssue.source),
    ):
        if values is not None:
            conditions.append(column.in_(values) if values else false())
    if occurred_at_from:
        conditions.append(AbnormalIssue.occurred_at >= occurred_at_from)
    if occurred_at_to:
        conditions.append(AbnormalIssue.occurred_at <= occurred_at_to)
    if external_record_id:
        conditions.append(
            AbnormalIssue.external_record_id == external_record_id
        )
    if keyword:
        conditions.append(
            or_(
                AbnormalIssue.issue_code.contains(keyword, autoescape=True),
                AbnormalIssue.issue_type_code.contains(keyword, autoescape=True),
                AbnormalIssue.title.contains(keyword, autoescape=True),
                AbnormalIssue.message.contains(keyword, autoescape=True),
                AbnormalIssue.device_code.contains(keyword, autoescape=True),
                Beam.beam_code.contains(keyword, autoescape=True),
            )
        )

    def joins(query):
        return query.outerjoin(Beam, Beam.id == AbnormalIssue.beam_id)

    base = joins(_statement()).where(*conditions)
    total = (
        session.scalar(
            joins(select(func.count()).select_from(AbnormalIssue)).where(
                *conditions
            )
        )
        if include_total
        else None
    )
    direction = asc if sort_order == "asc" else desc
    order = [direction(SORT_COLUMNS[sort_by])]
    if sort_by != "id":
        order.append(direction(AbnormalIssue.id))
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
