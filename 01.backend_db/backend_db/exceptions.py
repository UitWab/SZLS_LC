class BackendDBError(Exception):
    """数据库模块对外公开异常的统一基类。"""

    code = "backend_db_error"


class ResourceNotFoundError(BackendDBError):
    """请求的业务资源不存在。"""

    code = "resource_not_found"


class BeamNotFoundError(ResourceNotFoundError):
    code = "beam_not_found"


class BeamTypeNotFoundError(ResourceNotFoundError):
    code = "beam_type_not_found"


class BeamPositionNotFoundError(ResourceNotFoundError):
    code = "beam_position_not_found"


class YardAreaNotFoundError(ResourceNotFoundError):
    code = "yard_area_not_found"


class ResourceConflictError(BackendDBError):
    """操作与资源当前状态或唯一约束冲突。"""

    code = "resource_conflict"


class ResourceAlreadyExistsError(ResourceConflictError):
    code = "resource_already_exists"


class PositionOccupiedError(ResourceConflictError):
    code = "position_occupied"


class InvalidDataError(BackendDBError):
    """输入数据不符合数据库模块的业务约束。"""

    code = "invalid_data"


class InvalidBeamStatusError(InvalidDataError):
    code = "invalid_beam_status"


class DatabaseUnavailableError(BackendDBError):
    """数据库暂时不可访问。"""

    code = "database_unavailable"
