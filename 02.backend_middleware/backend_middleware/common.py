from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from secrets import compare_digest
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from backend_db.schemas import OperationAuditLogCreate

T = TypeVar("T")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Result(BaseModel, Generic[T]):
    data: T
    request_id: str
    warnings: list[str] = Field(default_factory=list)


class ActiveChange(Model):
    is_active: bool


def wire(value):
    """数据库 naive datetime 按 A 契约解释为 UTC；Decimal 以字符串无损传输。"""
    if isinstance(value, BaseModel):
        return wire(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(item) for item in value]
    return value


def result(request, data, warnings=None):
    from fastapi.responses import JSONResponse
    return JSONResponse(wire({"data": data, "request_id": request.state.request_id, "warnings": warnings or []}))


bearer = HTTPBearer(auto_error=False)


def authorize(*roles):
    def check(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        settings = request.app.state.settings
        if not any((settings.admin_key, settings.read_key, settings.plc_key)):
            raise HTTPException(503, "authentication_not_configured")
        if credentials:
            for role, expected in (("admin", settings.admin_key), ("reader", settings.read_key), ("plc", settings.plc_key)):
                if expected and compare_digest(credentials.credentials.encode(), expected.encode()):
                    if role not in roles:
                        raise HTTPException(403, "forbidden")
                    request.state.actor = role
                    return role
        raise HTTPException(401, "unauthorized", headers={"WWW-Authenticate": "Bearer"})
    return check


read_access = authorize("admin", "reader")
write_access = authorize("admin")
plc_access = authorize("admin", "plc")


def scope(request):
    return request.app.state.settings.project_code


def scoped(request, dto):
    """保持 PATCH 的 fields_set，并阻止调用方跨越部署项目作用域。"""
    values = dto.model_dump(exclude_unset=True)
    if "project_code" in type(dto).model_fields:
        if "project_code" in values and values["project_code"] != scope(request):
            raise HTTPException(403, "project_scope_mismatch")
        values["project_code"] = scope(request)
    if values.get("include_global"):
        raise HTTPException(403, "include_global_not_allowed")
    return type(dto).model_validate(values)


def mutate(request, service, method, *args, **kwargs):
    data = getattr(getattr(request.app.state.services, service), method)(*args, **kwargs)
    warnings = []
    # A 的两次 Service 调用是两个事务：审计失败不能把已提交业务伪装成失败。
    try:
        request.app.state.services.audit_logs.record(OperationAuditLogCreate(
            project_code=scope(request), actor_name="middleware:" + request.state.actor,
            action_code=f"{service}.{method}", resource_type=service,
            result_code="SUCCESS", request_id=request.state.request_id,
            source="MIDDLEWARE", occurred_at=datetime.now(timezone.utc),
        ))
    except Exception:
        warnings.append("audit_not_recorded")
    return result(request, data, warnings)
