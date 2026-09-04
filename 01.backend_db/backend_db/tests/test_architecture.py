from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _source_files(directory: str):
    return (PACKAGE_ROOT / directory).glob("*.py")


def test_schemas_do_not_depend_on_orm_or_sqlalchemy():
    for path in _source_files("schemas"):
        source = path.read_text(encoding="utf-8")
        assert "backend_db.models" not in source, path
        assert "sqlalchemy" not in source, path


def test_crud_does_not_depend_on_schemas_or_commit_transactions():
    for path in _source_files("crud"):
        source = path.read_text(encoding="utf-8")
        assert "backend_db.schemas" not in source, path
        assert ".commit(" not in source, path


def test_services_do_not_import_orm_models_or_sessions():
    for path in _source_files("services"):
        source = path.read_text(encoding="utf-8")
        assert "backend_db.models" not in source, path
        assert "sqlalchemy.orm" not in source, path


def test_interface_contracts_are_persistence_independent():
    path = PACKAGE_ROOT / "interfaces" / "contracts.py"
    source = path.read_text(encoding="utf-8")
    assert "backend_db.models" not in source
    assert "backend_db.crud" not in source
    assert "backend_db.services" not in source
    assert "sqlalchemy" not in source
