from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session

from backend_db.database.mysql import SessionLocal


SessionFactory = Callable[[], Session]


class UnitOfWork:
    """为一次 Service 调用提供明确的事务和 Session 边界。"""

    def __init__(self, session_factory: SessionFactory = SessionLocal):
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork 尚未进入上下文或已经关闭")

        return self._session

    def __enter__(self) -> "UnitOfWork":
        if self._session is not None:
            raise RuntimeError("UnitOfWork 不允许重复进入")

        self._session = self._session_factory()
        return self

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session

        if session is None:
            return

        try:
            if exc_type is not None or session.in_transaction():
                session.rollback()
        finally:
            session.close()
            self._session = None
