from sqlalchemy.exc import OperationalError, SQLAlchemyError

from backend_db.exceptions import BackendDBError, DatabaseUnavailableError


def raise_database_error(error: SQLAlchemyError) -> None:
    if isinstance(error, OperationalError):
        raise DatabaseUnavailableError("数据库暂时不可访问") from None
    raise BackendDBError("数据库操作失败") from None
