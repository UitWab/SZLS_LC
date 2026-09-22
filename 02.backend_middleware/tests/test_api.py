import ast
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend_db import exceptions as e, schemas as s
from backend_middleware.app import create_app
from backend_middleware.common import wire
from backend_middleware.config import Settings
from backend_middleware.resources import RESOURCES
from backend_middleware.telemetry import TelemetryReport, TelemetryStore
from simulator.plc import execution, send, telemetry
from conftest import ADMIN, READER, PLC


def page():
    return {"items": [], "page": 1, "page_size": 20, "total": 0, "has_next": False, "has_previous": False}


def test_auth_and_fail_closed(client):
    assert client.get("/health/live", headers={"Authorization": ""}).status_code == 200
    assert client.get("/api/v1/ue5/contract", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/v1/ue5/contract", headers={"Authorization": "Bearer " + PLC}).status_code == 403
    assert client.post("/api/v1/beams", json={}, headers={"Authorization": "Bearer " + READER}).status_code == 403
    with TestClient(create_app(object(), Settings())) as empty:
        assert empty.get("/api/v1/ue5/contract").status_code == 503


@pytest.mark.parametrize("definition", RESOURCES)
def test_all_list_and_search_routes(client, services, definition):
    path, attr, _, _, _, _ = definition
    service = getattr(services, attr)
    service.list.return_value = page()
    response = client.get("/api/v1/" + path)
    assert response.status_code == 200, response.text
    assert service.list.call_args.args[0].project_code == "P1"
    response = client.post("/api/v1/" + path + "/search", json={"pagination": {"page": 2, "page_size": 10}})
    assert response.status_code == 200, response.text
    assert service.list.call_args.args[1].page == 2
    assert client.get("/api/v1/" + path + "?page_size=101").status_code == 422


@pytest.mark.parametrize("error,code", [(e.BeamNotFoundError,404), (e.ResourceConflictError,409), (e.InvalidDataError,422), (e.DatabaseUnavailableError,503), (e.BackendDBError,500), (RuntimeError,500)])
def test_errors_redact_details(client, services, error, code):
    services.beams.get.side_effect = error("SECRET_DB_PASSWORD")
    response = client.get("/api/v1/beams/1")
    assert response.status_code == code
    assert "SECRET_DB_PASSWORD" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_scope_and_validation(client, services):
    assert client.post("/api/v1/beams/search", json={"filters":{"project_code":"OTHER"}}).status_code == 403
    assert client.post("/api/v1/beams/search", json={"filters":{"include_global":True}}).status_code == 403
    services.beams.list.assert_not_called()
    assert client.post("/api/v1/beams", json={"beam_code":"B1","beam_type_code":"T1","status":"BAD"}).status_code == 422
    services.beams.create.assert_not_called()


def test_partial_update_and_audit(client, services):
    services.beams.update.return_value = {"beam_code":"B1"}
    response = client.patch("/api/v1/beams/1", json={"remark":None})
    assert response.status_code == 200
    dto = services.beams.update.call_args.args[1]
    assert dto.model_fields_set == {"remark"}
    assert services.beams.update.call_args.kwargs == {"project_code":"P1"}
    audit = services.audit_logs.record.call_args.args[0]
    assert audit.project_code == "P1"
    assert audit.actor_name == "middleware:admin"
    services.audit_logs.record.side_effect = e.DatabaseUnavailableError()
    response = client.patch("/api/v1/beams/1", json={"beam_name":"test"})
    assert response.status_code == 200
    assert response.json()["warnings"] == ["audit_not_recorded"]


def test_create_and_status(client, services):
    services.beams.create.return_value = {"beam_code":"B1"}
    response = client.post("/api/v1/beams", json={"beam_code":"B1","beam_type_code":"T1"})
    assert response.status_code == 200
    assert services.beams.create.call_args.args[0].project_code == "P1"
    services.beams.change_status.return_value = {"status":"CURING"}
    assert client.post("/api/v1/beams/by-code/B1/status", json={"status":"CURING"}).status_code == 200
    assert services.beams.change_status.call_args.args[1].status == s.BeamStatus.CURING


def test_order_only_calls_atomic_public_command(client, services):
    for action in ("start","complete","cancel"):
        getattr(services.position_work_orders, action).return_value = {"work_order_code":"W1"}
        assert client.post(f"/api/v1/position-work-orders/by-code/W1/{action}").status_code == 200
        getattr(services.position_work_orders, action).assert_called_once_with("W1", project_code="P1")
    services.beams.move_beam.assert_not_called()
    services.beams.assign_position.assert_not_called()


def test_events_cursor_and_enums(client, services):
    services.beam_events.list_after.return_value = {"items":[],"next_cursor":"opaque-cursor","has_more":False}
    r = client.get("/api/v1/ue5/events?cursor=opaque-cursor&limit=5")
    assert r.status_code == 200
    filters, cursor = services.beam_events.list_after.call_args.args
    assert filters.project_code == "P1" and cursor.cursor == "opaque-cursor" and cursor.limit == 5
    assert client.get("/api/v1/meta/enums").json()["data"]["enums"]["BeamStatus"] == [v.value for v in s.BeamStatus]
    assert client.get("/api/v1/ue5/contract").json()["data"]["status"] == "PROVISIONAL"


def test_plc_roundtrip_idempotency_and_conflict(client, services):
    services.beams.get_by_code.return_value = {"beam_code":"B1"}
    body = telemetry("B1","PLC1","P1")
    headers = {"Authorization":"Bearer " + PLC}
    first = client.post("/api/v1/plc/telemetry", json=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["persisted"] is False
    assert client.post("/api/v1/plc/telemetry", json=body, headers=headers).json()["data"]["duplicate"]
    body["measurements"][0]["value"] += 1
    assert client.post("/api/v1/plc/telemetry", json=body, headers=headers).status_code == 409
    latest = client.get("/api/v1/ue5/telemetry/latest").json()["data"]
    assert len(latest["items"]) == 1
    body["project_code"] = "OTHER"
    assert client.post("/api/v1/plc/telemetry", json=body, headers=headers).status_code == 403
    body["project_code"] = "P1"
    body["measurements"][0]["unit"] = "BAD"
    assert client.post("/api/v1/plc/telemetry", json=body, headers=headers).status_code == 422


def test_plc_unknown_beam_and_process(client, services):
    services.beams.get_by_code.side_effect = e.BeamNotFoundError()
    assert client.post("/api/v1/plc/telemetry", json=telemetry("missing","PLC1","P1")).status_code == 404
    assert client.get("/api/v1/ue5/telemetry/latest").json()["data"]["items"] == []
    body = execution("B1","PLC1","CURING","P1")
    services.process_records.record.return_value = {"execution_code":body["execution_code"]}
    assert client.post("/api/v1/plc/process-records", json=body).status_code == 200
    assert services.process_records.record.call_args.args[0].source == s.RecordSource.DEVICE
    body["external_record_id"] = None
    assert client.post("/api/v1/plc/process-records", json=body).status_code == 422


def test_telemetry_bounded_concurrent_and_time(monkeypatch):
    cache = TelemetryStore(2, 10)
    body = TelemetryReport.model_validate(telemetry("B1","PLC1","P1"))
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: cache.put(body), range(20)))
    assert sum(not r["duplicate"] for r in results) == 1
    older = body.model_copy(update={"message_id":"older","observed_at":body.observed_at-timedelta(minutes=1)})
    cache.put(older)
    assert cache.latest("P1")["items"][0].message_id == body.message_id
    assert cache.latest("OTHER")["items"] == []
    cache.put(body.model_copy(update={"message_id":"third","device_id":"PLC2"}))
    assert len(cache._records) == 2
    monkeypatch.setattr("backend_middleware.telemetry.time.monotonic", lambda: 10**15)
    assert cache.latest("P1")["items"] == []


def test_wire_dates_and_precision():
    output = wire({"time":datetime(2026,1,1), "date":date(2026,1,1), "x":Decimal("1.123")})
    assert output == {"time":"2026-01-01T00:00:00Z","date":"2026-01-01","x":"1.123"}


def test_simulator_retry_preserves_message(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request.content)
        return httpx.Response(503 if len(requests) == 1 else 200, json={"ok":True})
    monkeypatch.setattr("simulator.plc.time.sleep", lambda _: None)
    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)) as client:
        assert send(client,"/report",telemetry("B1","PLC1")) == {"ok":True}
    assert requests[0] == requests[1]


def test_openapi_and_dependency_boundary(client):
    document = client.get("/openapi.json").json()
    assert len(document["paths"]) >= 50
    assert "BeamCreate" in document["components"]["schemas"]
    root = Path(__file__).resolve().parents[1]
    for folder in ("backend_middleware", "simulator"):
        for file in (root/folder).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
                imports = [node.module or ""] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
                for name in imports:
                    assert not name.startswith(("backend_db.models", "backend_db.crud", "backend_db.database", "backend_db.services", "sqlalchemy", "pymysql")), (file, name)


def test_factory_is_used(monkeypatch, services):
    calls = []
    monkeypatch.setattr("backend_middleware.app.create_database_services", lambda: calls.append(True) or services)
    with TestClient(create_app(settings=Settings(admin_key=ADMIN))):
        assert calls == [True]


@pytest.mark.parametrize("path,attr,payload", [
    ("beam-types", "beam_types", {"type_code":"T1","type_name":"32米梁"}),
    ("yard-areas", "yard_areas", {"area_code":"A1","area_name":"养护区","area_type":"CURING"}),
    ("beam-positions", "beam_positions", {"position_code":"POS1","area_code":"A1","x_mm":"1.123"}),
    ("processes", "processes", {"process_code":"CURING","process_name":"养护"}),
    ("position-work-orders", "position_work_orders", {"work_order_code":"W1","beam_code":"B1","order_type":"PLACE","target_position_code":"POS1"}),
])
def test_other_creates(client, services, path, attr, payload):
    service = getattr(services, attr)
    service.create.return_value = {"id":1}
    response = client.post("/api/v1/" + path, json=payload)
    assert response.status_code == 200, response.text
    assert service.create.call_args.args[0].project_code == "P1"
    services.audit_logs.record.assert_called_once()


@pytest.mark.parametrize("definition", RESOURCES)
def test_details_preserve_service_key(client, services, definition):
    path, attr, _, key_type, _, _ = definition
    key = 7 if key_type is int else "RECORD-7"
    service = getattr(services, attr)
    service.get.return_value = {"id":7}
    assert client.get(f"/api/v1/{path}/{key}").status_code == 200
    service.get.assert_called_once_with(key, project_code="P1")


@pytest.mark.parametrize("path,attr", [("beam-types","beam_types"),("yard-areas","yard_areas"),("beam-positions","beam_positions"),("processes","processes")])
def test_active(client, services, path, attr):
    getattr(services,attr).set_active.return_value = {"is_active":False}
    response = client.post(f"/api/v1/{path}/1/active", json={"is_active":False})
    assert response.status_code == 200
    getattr(services,attr).set_active.assert_called_once_with(1, is_active=False, project_code="P1")


@pytest.mark.parametrize("path,attr,example", [("process-records","process_records","process_record"), ("quality-records","quality_records","quality_record"), ("transport-records","transport_records","transport_record")])
def test_record_and_void_examples(client, services, path, attr, example):
    service = getattr(services,attr)
    service.record.return_value = {"id":1}
    payload = json.loads((Path(__file__).resolve().parents[1]/"docs"/"examples"/(example+".json")).read_text(encoding="utf-8"))
    response = client.post("/api/v1/"+path, json=payload)
    assert response.status_code == 200, response.text
    assert service.record.call_args.args[0].project_code == "P1"
    service.void.return_value = {"is_voided":True}
    assert client.post(f"/api/v1/{path}/RECORD-1/void", json={"voided_by_name":"admin","void_reason":"correction"}).status_code == 200
    assert service.void.call_args.args[0] == "RECORD-1"
    assert service.void.call_args.kwargs == {"project_code":"P1"}


def test_readiness_failure_and_current_project(client, services):
    services.projects.get_by_code.return_value = {"project_code":"P1"}
    assert client.get("/health/ready").status_code == 200
    services.projects.get_by_code.assert_called_with("P1")
    assert client.get("/api/v1/projects/current").json()["data"]["project_code"] == "P1"
    services.projects.get_by_code.side_effect = e.DatabaseUnavailableError()
    assert client.get("/health/ready").status_code == 503


def test_no_forbidden_operations(client):
    assert client.delete("/api/v1/beams/1").status_code == 405
    assert client.post("/api/v1/beam-events", json={}).status_code == 405
    assert client.patch("/api/v1/quality-records/Q1", json={}).status_code == 405


def test_time_precision_from_actual_read_dto(client, services):
    services.beams.get.return_value = s.BeamRead(
        id=1, beam_code="B1", beam_name=None, beam_type_code="T1", beam_type_name="T", project_code="P1",
        status="CURING", current_position_code=None, is_positioned=False, beam_type_id=1,
        current_position_id=None, current_position_name=None, current_area_code=None, current_area_name=None,
        production_date=date(2026,9,22), remark=None, created_at=datetime(2026,9,22), updated_at=datetime(2026,9,22))
    data = client.get("/api/v1/beams/1").json()["data"]
    assert data["production_date"] == "2026-09-22"
    assert data["created_at"].endswith("Z")


def test_global_scope_is_not_all_projects(services):
    services.beams.list.return_value = page()
    with TestClient(create_app(services,Settings(admin_key=ADMIN))) as client:
        client.headers["Authorization"] = "Bearer " + ADMIN
        assert client.get("/api/v1/beams").status_code == 200
        filters = services.beams.list.call_args.args[0]
        assert filters.project_code is None and filters.include_global is False


def test_invalid_measurements_and_execution_time(client):
    body = telemetry("B1","PLC1","P1")
    body["observed_at"] = "2026-09-22T08:00:00"
    assert client.post("/api/v1/plc/telemetry", json=body).status_code == 422
    body = execution("B1","PLC1","CURING","P1")
    body["finished_at"] = "2000-01-01T00:00:00Z"
    assert client.post("/api/v1/plc/process-records", json=body).status_code == 422


def test_unknown_fields_and_scope_null(client):
    assert client.post("/api/v1/beams/search", json={"extra":1}).status_code == 422
    assert client.post("/api/v1/beams/search", json={"filters":{"project_code":None}}).status_code == 403


def test_simulator_never_retries_conflict(monkeypatch):
    seen = []
    def handler(request):
        seen.append(True)
        return httpx.Response(409, json={"error":"conflict"})
    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            send(client,"/report",{})
    assert len(seen) == 1
