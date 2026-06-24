"""FastAPI application factory – wires up all middleware and routers."""
from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_ENV, CORS_ORIGINS, KAFKA_ENABLED
from .database import Base, engine
from .logging_config import configure_logging, StructLogger as _SL
get_logger = _SL
from .redis_client import rate_limit_check
from .routers import auth, git, repos
from .routers import pull_requests, oauth, registry, runners, scanner, signatures, kubernetes, dashboard
from .telemetry import setup_tracing

# ── configure logging first ───────────────────────────────────────────────────
configure_logging()
logger = get_logger(__name__)

Base.metadata.create_all(bind=engine)

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
async def request_middleware(request: Request, call_next) -> Response:
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limit_check(f"rl:{client_ip}", limit=120, window_seconds=60):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "http.request",
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
app.include_router(pull_requests.router)
app.include_router(oauth.router)
app.include_router(registry.router)
app.include_router(runners.router)
app.include_router(scanner.router)
app.include_router(signatures.router)
app.include_router(kubernetes.router)
app.include_router(dashboard.router)

try:
    from .graphql_schema import graphql_app, extended_graphql_app
    app.include_router(graphql_app, prefix="/graphql")
    app.include_router(extended_graphql_app, prefix="/graphql/extended")
    logger.info("graphql.mounted", path="/graphql")
except ImportError:
    logger.warning("graphql.strawberry_not_installed")


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


@app.get("/", tags=["health"])
def root() -> dict:
    return {"name": "stud-remote-server", "status": "ok", "version": "2.0.0"}


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
def ready() -> dict:
    """Kubernetes readiness probe."""
    import sqlalchemy
    checks: dict = {"db": "ok", "redis": "ok"}
    try:
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
    ok = all(v == "ok" for v in checks.values())
    from fastapi.responses import JSONResponse
    return JSONResponse(
        {"status": "ready" if ok else "degraded", **checks},
        status_code=200 if ok else 503,
    )
