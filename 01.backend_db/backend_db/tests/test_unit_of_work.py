from uuid import uuid4

import pytest
from sqlalchemy import select

from backend_db.database.mysql import SessionLocal
from backend_db.database.unit_of_work import UnitOfWork
from backend_db.models import BeamType


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.transaction_active = True

    def commit(self):
        self.committed = True
        self.transaction_active = False

    def rollback(self):
        self.rolled_back = True
        self.transaction_active = False

    def close(self):
        self.closed = True

    def in_transaction(self):
        return self.transaction_active


def test_unit_of_work_uses_one_session_and_closes_it_after_commit():
    fake_session = FakeSession()
    factory_calls = 0

    def session_factory():
        nonlocal factory_calls
        factory_calls += 1
        return fake_session

    with UnitOfWork(session_factory) as unit_of_work:
        assert unit_of_work.session is fake_session
        assert unit_of_work.session is fake_session
        unit_of_work.commit()

    assert factory_calls == 1
    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    assert fake_session.closed is True


def test_unit_of_work_rolls_back_when_context_exits_without_commit():
    fake_session = FakeSession()

    with UnitOfWork(lambda: fake_session):
        pass

    assert fake_session.committed is False
    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_unit_of_work_rolls_back_when_operation_raises():
    fake_session = FakeSession()

    with pytest.raises(ValueError, match="测试失败"):
        with UnitOfWork(lambda: fake_session):
            raise ValueError("测试失败")

    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_unit_of_work_rejects_session_access_outside_context():
    unit_of_work = UnitOfWork(lambda: FakeSession())

    with pytest.raises(RuntimeError, match="尚未进入"):
        _ = unit_of_work.session

    with unit_of_work:
        pass

    with pytest.raises(RuntimeError, match="已经关闭"):
        _ = unit_of_work.session


def test_uncommitted_database_changes_are_rolled_back():
    type_code = f"TEST_UOW_ROLLBACK_{uuid4().hex[:8]}"

    with UnitOfWork() as unit_of_work:
        unit_of_work.session.add(
            BeamType(
                type_code=type_code,
                type_name="事务回滚测试梁型",
                is_active=True,
            )
        )
        unit_of_work.session.flush()

    with SessionLocal() as session:
        result = session.scalar(
            select(BeamType).where(BeamType.type_code == type_code)
        )

    assert result is None


def test_committed_database_changes_are_persisted():
    type_code = f"TEST_UOW_COMMIT_{uuid4().hex[:8]}"

    try:
        with UnitOfWork() as unit_of_work:
            unit_of_work.session.add(
                BeamType(
                    type_code=type_code,
                    type_name="事务提交测试梁型",
                    is_active=True,
                )
            )
            unit_of_work.commit()

        with SessionLocal() as session:
            result = session.scalar(
                select(BeamType).where(BeamType.type_code == type_code)
            )

            assert result is not None
            assert result.type_name == "事务提交测试梁型"
    finally:
        with SessionLocal.begin() as session:
            result = session.scalar(
                select(BeamType).where(BeamType.type_code == type_code)
            )

            if result is not None:
                session.delete(result)
