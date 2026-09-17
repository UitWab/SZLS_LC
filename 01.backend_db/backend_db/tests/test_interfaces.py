import inspect
from typing import get_type_hints

from backend_db.interfaces import (
    AccessControlServiceProtocol,
    BeamPositionServiceProtocol,
    BeamPositionWorkOrderServiceProtocol,
    BeamLifecycleEventServiceProtocol,
    BeamProcessExecutionServiceProtocol,
    BeamQualityInspectionServiceProtocol,
    BeamTransportHandoverServiceProtocol,
    BeamServiceProtocol,
    BeamTypeServiceProtocol,
    ProjectServiceProtocol,
    OperationAuditLogServiceProtocol,
    ProcessDefinitionServiceProtocol,
    UserServiceProtocol,
    YardAreaServiceProtocol,
    create_database_services,
)


def test_public_factory_returns_all_service_contracts():
    services = create_database_services()

    assert isinstance(services.projects, ProjectServiceProtocol)
    assert isinstance(services.audit_logs, OperationAuditLogServiceProtocol)
    assert isinstance(services.processes, ProcessDefinitionServiceProtocol)
    assert isinstance(services.users, UserServiceProtocol)
    assert isinstance(services.access_control, AccessControlServiceProtocol)
    assert isinstance(services.beam_types, BeamTypeServiceProtocol)
    assert isinstance(services.yard_areas, YardAreaServiceProtocol)
    assert isinstance(services.beam_positions, BeamPositionServiceProtocol)
    assert isinstance(services.position_work_orders, BeamPositionWorkOrderServiceProtocol)
    assert isinstance(services.beam_events, BeamLifecycleEventServiceProtocol)
    assert isinstance(services.process_records, BeamProcessExecutionServiceProtocol)
    assert isinstance(services.quality_records, BeamQualityInspectionServiceProtocol)
    assert isinstance(services.transport_records, BeamTransportHandoverServiceProtocol)
    assert isinstance(services.beams, BeamServiceProtocol)


def test_public_beam_contract_has_no_delete_operation():
    services = create_database_services()
    assert not hasattr(services.beams, "delete")
    assert not hasattr(services.beams, "archive")


def test_public_v2_contracts_have_no_physical_delete_operation():
    services = create_database_services()

    for service in (
        services.projects,
        services.audit_logs,
        services.processes,
        services.users,
        services.access_control,
    ):
        assert not hasattr(service, "delete")


def test_public_audit_log_contract_is_append_only():
    audit_logs = create_database_services().audit_logs
    assert hasattr(audit_logs, "record")
    assert hasattr(audit_logs, "get")
    assert hasattr(audit_logs, "list")
    assert not hasattr(audit_logs, "update")
    assert not hasattr(audit_logs, "set_active")
    assert not hasattr(audit_logs, "delete")


def test_public_position_work_order_contract_has_no_direct_update_or_delete():
    work_orders = create_database_services().position_work_orders
    assert hasattr(work_orders, "create")
    assert hasattr(work_orders, "start")
    assert hasattr(work_orders, "complete")
    assert hasattr(work_orders, "cancel")
    assert not hasattr(work_orders, "update")
    assert not hasattr(work_orders, "delete")


def test_public_beam_lifecycle_event_contract_is_read_only():
    events = create_database_services().beam_events
    assert hasattr(events, "get")
    assert hasattr(events, "list")
    assert hasattr(events, "list_after")
    assert not hasattr(events, "record")
    assert not hasattr(events, "create")
    assert not hasattr(events, "update")
    assert not hasattr(events, "set_active")
    assert not hasattr(events, "delete")


def test_public_protocol_annotations_can_be_resolved():
    protocols = (
        AccessControlServiceProtocol,
        BeamTypeServiceProtocol,
        ProjectServiceProtocol,
        OperationAuditLogServiceProtocol,
        ProcessDefinitionServiceProtocol,
        UserServiceProtocol,
        YardAreaServiceProtocol,
        BeamPositionServiceProtocol,
        BeamPositionWorkOrderServiceProtocol,
        BeamLifecycleEventServiceProtocol,
        BeamProcessExecutionServiceProtocol,
        BeamQualityInspectionServiceProtocol,
        BeamTransportHandoverServiceProtocol,
        BeamServiceProtocol,
    )

    for protocol in protocols:
        for _, method in inspect.getmembers(protocol, inspect.isfunction):
            get_type_hints(method)
