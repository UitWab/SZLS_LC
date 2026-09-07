import inspect
from typing import get_type_hints

from backend_db.interfaces import (
    AccessControlServiceProtocol,
    BeamPositionServiceProtocol,
    BeamServiceProtocol,
    BeamTypeServiceProtocol,
    ProjectServiceProtocol,
    ProcessDefinitionServiceProtocol,
    UserServiceProtocol,
    YardAreaServiceProtocol,
    create_database_services,
)


def test_public_factory_returns_all_service_contracts():
    services = create_database_services()

    assert isinstance(services.projects, ProjectServiceProtocol)
    assert isinstance(services.processes, ProcessDefinitionServiceProtocol)
    assert isinstance(services.users, UserServiceProtocol)
    assert isinstance(services.access_control, AccessControlServiceProtocol)
    assert isinstance(services.beam_types, BeamTypeServiceProtocol)
    assert isinstance(services.yard_areas, YardAreaServiceProtocol)
    assert isinstance(services.beam_positions, BeamPositionServiceProtocol)
    assert isinstance(services.beams, BeamServiceProtocol)


def test_public_beam_contract_has_no_delete_operation():
    services = create_database_services()
    assert not hasattr(services.beams, "delete")
    assert not hasattr(services.beams, "archive")


def test_public_v2_contracts_have_no_physical_delete_operation():
    services = create_database_services()

    for service in (
        services.projects,
        services.processes,
        services.users,
        services.access_control,
    ):
        assert not hasattr(service, "delete")


def test_public_protocol_annotations_can_be_resolved():
    protocols = (
        AccessControlServiceProtocol,
        BeamTypeServiceProtocol,
        ProjectServiceProtocol,
        ProcessDefinitionServiceProtocol,
        UserServiceProtocol,
        YardAreaServiceProtocol,
        BeamPositionServiceProtocol,
        BeamServiceProtocol,
    )

    for protocol in protocols:
        for _, method in inspect.getmembers(protocol, inspect.isfunction):
            get_type_hints(method)
