from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import APP_ENV, CORS_ORIGINS, KAFKA_ENABLED, MAX_UPLOAD_BYTES
from .logging_config import configure_logging, StructLogger as _SL
from .redis_client import rate_limit_check
from .routers import auth, git, repos
from .telemetry import setup_tracing

configure_logging()
logger = _SL(__name__)

# NOTE: Base.metadata.create_all() removed — use `alembic upgrade head` instead.

app = FastAPI(
    title="Stud Remote Server",
    version="2.0.0",
    description="VCS hosting API with GraphQL, Kafka events, and OpenTelemetry tracing.",
    docs_url="/docs" if APP_ENV != "production" else None,
    redoc_url="/redoc" if APP_ENV != "production" else None,
)

setup_tracing(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    # rate limiting
    if not rate_limit_check(f"rl:{client_ip}", limit=120, window_seconds=60):
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)

    # upload size guard
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        return JSONResponse({"detail": "request body too large"}, status_code=413)

    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    # security headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    logger.info(
        "http.request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        ip=client_ip,
    )
    return response


app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(git.router)

try:
    from .graphql_schema import graphql_app
    app.include_router(graphql_app, prefix="/graphql")
    logger.info("graphql.mounted", path="/graphql")
except ImportError:
    logger.warning("graphql.strawberry_not_installed")

# ── metrics ───────────────────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("prometheus.metrics.exposed", path="/metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed; /metrics unavailable")


# ── lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    if KAFKA_ENABLED:
        from .kafka_client import get_producer
        get_producer()
    logger.info("app.started", env=APP_ENV)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if KAFKA_ENABLED:
        from .kafka_client import get_producer
        get_producer().close()
    logger.info("app.stopped")


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def root() -> dict:
    return {"name": "stud-remote-server", "status": "ok", "version": "2.0.0"}


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
def ready() -> dict:
    import sqlalchemy
    checks: dict = {"db": "ok", "redis": "ok", "kafka": "ok"}

    try:
        from .database import engine
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
    except Exception as exc:
        checks["db"] = str(exc)

    try:
        from .redis_client import _get_client
        if _get_client() is None:
            checks["redis"] = "unavailable"
    except Exception as exc:
        checks["redis"] = str(exc)

    if KAFKA_ENABLED:
        try:
            from .kafka_client import get_producer
            if not get_producer().is_ready():
                checks["kafka"] = "unavailable"
        except Exception as exc:
            checks["kafka"] = str(exc)
    else:
        checks["kafka"] = "disabled"

    ok = all(v in ("ok", "disabled") for v in checks.values())
    return JSONResponse(
        {"status": "ready" if ok else "degraded", **checks},
        status_code=200 if ok else 503,
    )
