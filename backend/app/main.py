import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import (
    administration,
    auth,
    availability,
    exports,
    imports,
    reference,
    timetables,
)
from app.config import settings
from app.db import SessionLocal

app = FastAPI(title="TimeForge", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().allowed_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings().trusted_hosts.split(","))
for router in [
    auth.router,
    reference.router,
    administration.router,
    timetables.router,
    imports.router,
    exports.router,
    availability.router,
]:
    app.include_router(router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    length = request.headers.get("content-length", "0")
    if not length.isdigit() or int(length) > settings().max_import_bytes + 100000:
        return JSONResponse({"detail": "Request is too large"}, status_code=413)
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Cache-Control": "no-store",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    if settings().cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        {"detail": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]},
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        {"detail": "A unique value already exists or this record is referenced by other data"},
        status_code=409,
    )


@app.exception_handler(StaleDataError)
async def stale_error(request: Request, exc: StaleDataError):
    return JSONResponse(
        {"detail": "This record changed in another session. Reload and retry."},
        status_code=409,
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger("timeforge").error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(
        {"detail": "The data service is unavailable. Please retry later."},
        status_code=503,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "timeforge"}


@app.get("/api/ready")
def ready():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        db.execute(text("SELECT version_num FROM alembic_version"))
    if not settings().jobs_eager:
        from redis import Redis

        try:
            Redis.from_url(settings().redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        except Exception:
            return JSONResponse(
                {"status": "not_ready", "detail": "Queue unavailable"}, status_code=503
            )
    return {"status": "ready"}
