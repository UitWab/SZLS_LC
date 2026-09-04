import inspect
from typing import get_type_hints

from backend_db.interfaces import (
    BeamPositionServiceProtocol,
    BeamServiceProtocol,
    BeamTypeServiceProtocol,
    YardAreaServiceProtocol,
    create_database_services,
)


def test_public_factory_returns_all_service_contracts():
    services = create_database_services()

    assert isinstance(services.beam_types, BeamTypeServiceProtocol)
    assert isinstance(services.yard_areas, YardAreaServiceProtocol)
    assert isinstance(services.beam_positions, BeamPositionServiceProtocol)
    assert isinstance(services.beams, BeamServiceProtocol)


def test_public_beam_contract_has_no_delete_operation():
    services = create_database_services()
    assert not hasattr(services.beams, "delete")
    assert not hasattr(services.beams, "archive")


def test_public_protocol_annotations_can_be_resolved():
    protocols = (
        BeamTypeServiceProtocol,
        YardAreaServiceProtocol,
        BeamPositionServiceProtocol,
        BeamServiceProtocol,
    )

    for protocol in protocols:
        for _, method in inspect.getmembers(protocol, inspect.isfunction):
            get_type_hints(method)
