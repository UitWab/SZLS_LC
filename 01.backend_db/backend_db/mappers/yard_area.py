from backend_db.models import YardArea
from backend_db.schemas import YardAreaRead, YardAreaSummary


def yard_area_to_summary(area: YardArea) -> YardAreaSummary:
    return YardAreaSummary(
        id=area.id,
        area_code=area.area_code,
        area_name=area.area_name,
        area_type=area.area_type,
        parent_area_code=area.parent.area_code if area.parent else None,
        is_active=area.is_active,
    )


def yard_area_to_read(area: YardArea) -> YardAreaRead:
    return YardAreaRead(
        **yard_area_to_summary(area).model_dump(),
        parent_id=area.parent_id,
        sort_order=area.sort_order,
        remark=area.remark,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )
