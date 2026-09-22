from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend_db import schemas as s
from .common import Result, mutate, plc_access, read_access, result, scope, scoped, write_access
from .telemetry import Metric, TelemetryReport, UNITS


def make_routes():
    router = APIRouter()

    @router.get("/meta/enums", dependencies=[Depends(read_access)], tags=["contract"])
    def enums(request: Request):
        values = {name: [item.value for item in cls] for name in s.__all__
                  if isinstance((cls := getattr(s, name)), type) and issubclass(cls, Enum)}
        return result(request, {"database_contract": "8.0.0", "enums": values,
            "beam_status_labels": s.BEAM_STATUS_LABELS, "Metric": list(Metric), "units": UNITS})

    @router.get("/projects/current", dependencies=[Depends(read_access)], tags=["projects"])
    def project(request: Request):
        code = scope(request)
        return result(request, request.app.state.services.projects.get_by_code(code) if code else {"project_code": None, "scope": "GLOBAL"})

    @router.get("/yard-tree", dependencies=[Depends(read_access)], response_model=Result[list[s.YardAreaTreeNode]], tags=["yard-areas"])
    def tree(request: Request):
        return result(request, request.app.state.services.yard_areas.tree(project_code=scope(request), include_global=False))

    @router.post("/beams/by-code/{beam_code}/status", dependencies=[Depends(write_access)], response_model=Result[s.BeamRead], tags=["beams"])
    def status(beam_code: str, body: s.BeamStatusChange, request: Request):
        return mutate(request, "beams", "change_status", beam_code, body, project_code=scope(request))

    @router.get("/beams/by-code/{beam_code}", dependencies=[Depends(read_access)], response_model=Result[s.BeamRead], tags=["beams"])
    def beam(beam_code: str, request: Request):
        return result(request, request.app.state.services.beams.get_by_code(beam_code, project_code=scope(request)))

    def order_action(action):
        def execute(work_order_code: str, request: Request):
            return mutate(request, "position_work_orders", action, work_order_code, project_code=scope(request))
        return execute

    for action in ("start", "complete", "cancel"):
        router.add_api_route(f"/position-work-orders/by-code/{{work_order_code}}/{action}", order_action(action),
            methods=["POST"], dependencies=[Depends(write_access)], response_model=Result[s.BeamPositionWorkOrderRead], tags=["position-work-orders"])

    @router.post("/plc/telemetry", dependencies=[Depends(plc_access)], tags=["plc"])
    def telemetry(body: TelemetryReport, request: Request):
        body = scoped(request, body)
        # 验证梁存在于本部署项目；PLC 测点不改变梁状态。
        request.app.state.services.beams.get_by_code(body.beam_code, project_code=scope(request))
        return result(request, request.app.state.telemetry.put(body))

    @router.post("/plc/process-records", dependencies=[Depends(plc_access)], response_model=Result[s.BeamProcessExecutionRead], tags=["plc"])
    def process_report(body: s.BeamProcessExecutionCreate, request: Request):
        if body.source != s.RecordSource.DEVICE or not body.external_record_id:
            raise HTTPException(422, "device_source_and_external_record_id_required")
        return mutate(request, "process_records", "record", scoped(request, body))

    @router.get("/ue5/contract", dependencies=[Depends(read_access)], tags=["ue5"])
    def contract(request: Request):
        return result(request, {"version": "1.0.0", "status": "PROVISIONAL", "project_code": scope(request),
            "transport": "HTTP_JSON_POLLING", "time": "UTC_ISO8601", "coordinate_unit": "mm",
            "coordinate_transform": "UNCONFIRMED", "decimal_encoding": "string", "id_encoding": "integer",
            "events": "/api/v1/ue5/events", "beams": "/api/v1/beams",
            "positions": "/api/v1/beam-positions", "telemetry": "/api/v1/ue5/telemetry/latest",
            "telemetry_persistent": False, "snapshot_atomic": False})

    @router.get("/ue5/events", dependencies=[Depends(read_access)], response_model=Result[s.CursorPageResult[s.BeamLifecycleEventSummary]], tags=["ue5"])
    def events(request: Request, cursor: str | None = Query(None, max_length=512), limit: int = Query(100, ge=1, le=100)):
        return result(request, request.app.state.services.beam_events.list_after(
            s.BeamLifecycleEventFilter(project_code=scope(request)), s.CursorPageRequest(cursor=cursor, limit=limit)))

    @router.get("/ue5/telemetry/latest", dependencies=[Depends(read_access)], tags=["ue5"])
    def latest(request: Request, beam_code: str | None = Query(None, min_length=1, max_length=64),
               device_id: str | None = Query(None, min_length=1, max_length=64), limit: int = Query(100, ge=1, le=100)):
        return result(request, request.app.state.telemetry.latest(scope(request), beam_code, device_id, limit))

    @router.get("/audit-logs", dependencies=[Depends(write_access)], response_model=Result[s.PageResult[s.OperationAuditLogSummary]], tags=["audit"])
    def audits(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        code = scope(request)
        filters = s.OperationAuditLogFilter(scope=s.OperationAuditLogScope.PROJECT if code else s.OperationAuditLogScope.SYSTEM, project_code=code)
        return result(request, request.app.state.services.audit_logs.list(filters, s.PageRequest(page=page, page_size=page_size)))

    return router
