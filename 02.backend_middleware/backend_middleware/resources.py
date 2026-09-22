"""为固定白名单 Service 生成强类型 HTTP 路由，不提供任意方法调用入口。"""
from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import Field, create_model

from backend_db import schemas as s
from .common import ActiveChange, Model, Result, mutate, read_access, result, scope, scoped, write_access

# URL、公开 Service、DTO 前缀、详情键类型、创建方法、是否支持 PATCH。
RESOURCES = (
    ("beam-types", "beam_types", "BeamType", int, "create", True),
    ("yard-areas", "yard_areas", "YardArea", int, "create", True),
    ("beam-positions", "beam_positions", "BeamPosition", int, "create", True),
    ("beams", "beams", "Beam", int, "create", True),
    ("processes", "processes", "ProcessDefinition", int, "create", True),
    ("position-work-orders", "position_work_orders", "BeamPositionWorkOrder", int, "create", False),
    ("beam-events", "beam_events", "BeamLifecycleEvent", int, None, False),
    ("process-records", "process_records", "BeamProcessExecution", str, "record", False),
    ("quality-records", "quality_records", "BeamQualityInspection", str, "record", False),
    ("transport-records", "transport_records", "BeamTransportHandover", str, "record", False),
)


def resource_router(path, service_name, prefix, key_type, create_method, updatable):
    router = APIRouter(prefix=f"/{path}", tags=[path])
    filter_type = getattr(s, prefix + "Filter")
    read_type = getattr(s, prefix + "Read")
    summary_type = getattr(s, prefix + "Summary")
    sort_type = getattr(s, prefix + "SortField")
    search_type = create_model(prefix + "Search", __base__=Model,
        filters=(filter_type, Field(default_factory=filter_type)),
        pagination=(s.PageRequest, Field(default_factory=s.PageRequest)),
        sort_by=(sort_type, sort_type.ID), sort_order=(s.SortOrder, s.SortOrder.ASC))

    def listing(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        filters = scoped(request, filter_type())
        return result(request, getattr(request.app.state.services, service_name).list(
            filters, s.PageRequest(page=page, page_size=page_size), sort_by=sort_type.ID, sort_order=s.SortOrder.ASC))

    def search(body: search_type, request: Request):
        return result(request, getattr(request.app.state.services, service_name).list(
            scoped(request, body.filters), body.pagination, sort_by=body.sort_by, sort_order=body.sort_order))

    def detail(request: Request, key: key_type = Path(...)):
        if isinstance(key, int) and key < 1:
            from fastapi import HTTPException
            raise HTTPException(422, "invalid_id")
        return result(request, getattr(request.app.state.services, service_name).get(key, project_code=scope(request)))

    router.add_api_route("", listing, methods=["GET"], response_model=Result[s.PageResult[summary_type]], dependencies=[Depends(read_access)])
    router.add_api_route("/search", search, methods=["POST"], response_model=Result[s.PageResult[summary_type]], dependencies=[Depends(read_access)])
    router.add_api_route("/{key}", detail, methods=["GET"], response_model=Result[read_type], dependencies=[Depends(read_access)])

    if create_method:
        create_type = getattr(s, prefix + "Create")
        def create(body: create_type, request: Request):
            return mutate(request, service_name, create_method, scoped(request, body))
        router.add_api_route("", create, methods=["POST"], response_model=Result[read_type], dependencies=[Depends(write_access)])

    if updatable:
        update_type = getattr(s, prefix + "Update")
        def update(body: update_type, request: Request, key: int = Path(..., ge=1)):
            return mutate(request, service_name, "update", key, scoped(request, body), project_code=scope(request))
        router.add_api_route("/{key}", update, methods=["PATCH"], response_model=Result[read_type], dependencies=[Depends(write_access)])
        if service_name != "beams":
            def active(body: ActiveChange, request: Request, key: int = Path(..., ge=1)):
                return mutate(request, service_name, "set_active", key, is_active=body.is_active, project_code=scope(request))
            router.add_api_route("/{key}/active", active, methods=["POST"], response_model=Result[read_type], dependencies=[Depends(write_access)])

    if create_method == "record":
        void_type = getattr(s, prefix + "Void")
        def void(body: void_type, request: Request, key: str):
            return mutate(request, service_name, "void", key, body, project_code=scope(request))
        router.add_api_route("/{key}/void", void, methods=["POST"], response_model=Result[read_type], dependencies=[Depends(write_access)])
    return router


def make_resources():
    router = APIRouter()
    for definition in RESOURCES:
        router.include_router(resource_router(*definition))
    return router
