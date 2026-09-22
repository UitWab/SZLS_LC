from dataclasses import fields
from typing import get_type_hints
from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from backend_db.interfaces.contracts import DatabaseServices
from backend_middleware.app import create_app
from backend_middleware.config import Settings

ADMIN = "test-admin-key-00000001"
READER = "test-reader-key-0000001"
PLC = "test-plc-key-0000000001"


@pytest.fixture
def services():
    hints = get_type_hints(DatabaseServices)
    return DatabaseServices(**{f.name: create_autospec(hints[f.name], instance=True) for f in fields(DatabaseServices)})


@pytest.fixture
def client(services):
    settings = Settings(admin_key=ADMIN, read_key=READER, plc_key=PLC, project_code="P1")
    with TestClient(create_app(services, settings), raise_server_exceptions=False) as client:
        client.headers["Authorization"] = "Bearer " + ADMIN
        yield client
