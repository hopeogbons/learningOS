import importlib
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text, select, func
from .settings import settings
from .db import SessionLocal, utcnow, as_utc
from .models import WorkerHeartbeat
from .core_schemas import ErrorEnvelopeDTO, HealthDTO, ReadinessDTO

@asynccontextmanager
async def lifespan(app):
    settings.validate()
    yield

app = FastAPI(title="Learning OS API", version=settings.version, lifespan=lifespan, responses={code: {"model": ErrorEnvelopeDTO} for code in (400, 401, 403, 404, 409, 413, 422, 429, 503)})
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, session_cookie="learningos_oidc_state", same_site="lax", https_only=settings.app_mode == "production", max_age=600)

@app.middleware("http")
async def request_id(request, call_next):
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

def error_response(request, status, code, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": code.replace("_", " "), "retryable": status in {429, 503}, "request_id": getattr(request.state, "request_id", None), "details": details or {}}})

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc):
    response = error_response(request, exc.status_code, str(exc.detail) if isinstance(exc.detail, str) else exc.detail.get("code", "request_failed"))
    if exc.headers:
        response.headers.update(exc.headers)
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    # Validation input may contain private answers/uploads; don't echo raw values.
    return error_response(request, 422, "invalid_request", {"fields": [".".join(map(str, e["loc"])) for e in exc.errors()]})

@app.exception_handler(Exception)
async def unknown_error(request: Request, exc):
    logging.getLogger("learningos").error("request_failed request_id=%s type=%s", getattr(request.state, "request_id", "unknown"), type(exc).__name__)
    return error_response(request, 500, "internal_error")

@app.get("/api/v1/health", response_model=HealthDTO)
def health():
    return {"status": "ok", "mode": settings.app_mode, "version": settings.version}

@app.get("/api/v1/ready", response_model=ReadinessDTO)
def ready():
    dependencies = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            migration = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            dependencies["database"] = "ready" if migration == "0002_durable_guards" else "migration-required"
            heartbeat = db.scalar(select(func.max(WorkerHeartbeat.checked_at)))
            dependencies["worker"] = "ready" if heartbeat and (utcnow() - as_utc(heartbeat)).total_seconds() < settings.worker_freshness_seconds else "stale"
    except Exception:
        dependencies["database"] = "unavailable"
    offline=settings.app_mode in {"demo","test"}
    dependencies["model"] = "offline-demo" if offline else "configured-unverified" if settings.api_key and settings.model else "unconfigured"
    if not offline:
        from .sources.drive import connection_setup_state
        dependencies["oidc"] = "configured-unverified" if (all((settings.oidc_issuer, settings.oidc_client_id, settings.oidc_client_secret))
            and settings.oidc_issuer.startswith('https://') and len(settings.session_secret)>=32
            and not settings.session_secret.startswith('local-demo')) else "unconfigured"
        dependencies["drive"] = "configured-unverified" if connection_setup_state()=='ready' else "unconfigured"
    if settings.app_mode == "production":
        dependencies["storage"] = "configured-unverified" if settings.s3_bucket else "unconfigured"
    ok = dependencies.get("database") == "ready" and dependencies.get("worker") == "ready" and dependencies.get("model") in {"offline-demo", "configured-unverified"}
    if not offline:
        ok = ok and dependencies.get('oidc')=='configured-unverified'
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "not-ready", "mode": settings.app_mode, "dependencies": dependencies})

for name in ("auth", "core_api", "learning_api", "ingestion_api"):
    try:
        module = importlib.import_module("app." + name)
    except ModuleNotFoundError as exc:
        if exc.name == "app." + name:
            continue
        raise
    app.include_router(module.router, prefix="/api/v1")
