from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from backend_db.database.mysql import SessionLocal
from backend_db.models import (
    Beam,
    BeamPosition,
    BeamType,
    YardArea,
)


def _suffix() -> str:
    """生成测试数据唯一后缀，避免不同测试之间发生业务编码冲突。"""
    return uuid4().hex[:8]


def _create_basic_data(session):
    """
    创建约束测试所需的最小基础数据。

    所有测试最终都会 rollback，
    因此不会污染开发数据库。
    """
    suffix = _suffix()

    area = YardArea(
        area_code=f"TEST_AREA_{suffix}",
        area_name="测试区域",
        area_type="test",
        sort_order=0,
        is_active=True,
    )

    beam_type = BeamType(
        type_code=f"TEST_TYPE_{suffix}",
        type_name="测试梁型",
        is_active=True,
    )

    session.add_all([area, beam_type])
    session.flush()

    position_1 = BeamPosition(
        position_code=f"TEST_POS_A_{suffix}",
        position_name="测试梁位A",
        area_id=area.id,
        is_active=True,
    )

    position_2 = BeamPosition(
        position_code=f"TEST_POS_B_{suffix}",
        position_name="测试梁位B",
        area_id=area.id,
        is_active=True,
    )

    session.add_all([position_1, position_2])
    session.flush()

    return beam_type, position_1, position_2


def test_beam_code_must_be_unique():
    """数据库必须拒绝重复 beam_code。"""

    session = SessionLocal()

    try:
        beam_type, position_1, position_2 = _create_basic_data(session)

        suffix = _suffix()
        beam_code = f"TEST_BEAM_{suffix}"

        beam_1 = Beam(
            beam_code=beam_code,
            beam_type_id=beam_type.id,
            current_position_id=position_1.id,
            status="test",
        )

        session.add(beam_1)
        session.flush()

        beam_2 = Beam(
            beam_code=beam_code,
            beam_type_id=beam_type.id,
            current_position_id=position_2.id,
            status="test",
        )

        session.add(beam_2)

        with pytest.raises(IntegrityError):
            session.flush()

    finally:
        session.rollback()
        session.close()


def test_one_position_can_only_hold_one_beam():
    """数据库必须拒绝两片梁同时占用同一梁位。"""

    session = SessionLocal()

    try:
        beam_type, position_1, _ = _create_basic_data(session)

        suffix = _suffix()

        beam_1 = Beam(
            beam_code=f"TEST_BEAM_A_{suffix}",
            beam_type_id=beam_type.id,
            current_position_id=position_1.id,
            status="test",
        )

        session.add(beam_1)
        session.flush()

        beam_2 = Beam(
            beam_code=f"TEST_BEAM_B_{suffix}",
            beam_type_id=beam_type.id,
            current_position_id=position_1.id,
            status="test",
        )

        session.add(beam_2)

        with pytest.raises(IntegrityError):
            session.flush()

    finally:
        session.rollback()
        session.close()


def test_beam_type_foreign_key_must_exist():
    """数据库必须拒绝不存在的 beam_type_id。"""

    session = SessionLocal()

    try:
        suffix = _suffix()

        beam = Beam(
            beam_code=f"TEST_INVALID_FK_{suffix}",
            beam_type_id=9_000_000_000_000_000_000,
            current_position_id=None,
            status="test",
        )

        session.add(beam)

        with pytest.raises(IntegrityError):
            session.flush()

    finally:
        session.rollback()
        session.close()