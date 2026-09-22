from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from backend_db import exceptions as errors
from backend_db.interfaces import create_database_services
from backend_db.schemas import PageRequest, ProjectFilter

from .common import read_access, result, scope
from .config import Settings
from .resources import make_resources
from .routes import make_routes
from .telemetry import TelemetryStore


def create_app(services=None, settings=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.services = services if services is not None else create_database_services()
        yield

    app = FastAPI(title="智慧梁场中介服务", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.telemetry = TelemetryStore(settings.telemetry_capacity, settings.telemetry_ttl_seconds)

    @app.middleware("http")
    async def request_context(request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    def failure(request, status, code, details=None, headers=None):
        request_id = getattr(request.state, "request_id", uuid4().hex)
        return JSONResponse(status_code=status, content={"error": {"code": code, "details": details or []}, "request_id": request_id},
                            headers={"X-Request-ID": request_id, **(headers or {})})

    @app.exception_handler(errors.BackendDBError)
    async def database_error(request: Request, exc):
        status = 500
        for cls, http_status in ((errors.ResourceNotFoundError, 404), (errors.ResourceConflictError, 409),
                                 (errors.InvalidDataError, 422), (errors.DatabaseUnavailableError, 503)):
            if isinstance(exc, cls):
                status = http_status
                break
        return failure(request, status, exc.code)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(request: Request, exc):
        # 不返回原始输入、数据库连接串或验证上下文。
        details = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return failure(request, 422, "validation_error", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        return failure(request, exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc):
        return failure(request, 500, "internal_error")

    @app.get("/health/live", tags=["health"])
    def live(request: Request):
        return result(request, {"status": "alive"})

    @app.get("/health/ready", dependencies=[Depends(read_access)], tags=["health"])
    def ready(request: Request):
        code = scope(request)
        if code:
            request.app.state.services.projects.get_by_code(code)
        else:
            request.app.state.services.projects.list(ProjectFilter(), PageRequest(page_size=1))
        return result(request, {"status": "ready", "database_contract": "8.0.0"})

    app.include_router(make_routes(), prefix="/api/v1")
    app.include_router(make_resources(), prefix="/api/v1")
    return app
