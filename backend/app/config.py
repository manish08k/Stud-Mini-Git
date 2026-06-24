from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APP_ENV: str = os.environ.get("APP_ENV", "development")
DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ── validate secrets in production ────────────────────────────────────────────
if APP_ENV == "production":
    _UNSAFE_DEFAULTS = {"dev-secret-change-me", "CHANGE_ME_64_CHARS_RANDOM", ""}
    if SECRET_KEY in _UNSAFE_DEFAULTS:
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production")
    if len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters in production")

DATA_DIR = Path(os.environ.get("STUD_SERVER_DATA", BACKEND_DIR / "data"))
REPOS_DIR = DATA_DIR / "repos"
DATABASE_PATH = DATA_DIR / "stud_server.db"
DATABASE_URL: str = os.environ.get("STUD_SERVER_DB_URL", f"sqlite:///{DATABASE_PATH}")

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

KAFKA_BOOTSTRAP_SERVERS: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_EVENTS: str = os.environ.get("KAFKA_TOPIC_EVENTS", "stud.events")
KAFKA_CONSUMER_GROUP: str = os.environ.get("KAFKA_CONSUMER_GROUP", "stud-backend")
KAFKA_ENABLED: bool = os.environ.get("KAFKA_ENABLED", "false").lower() == "true"
KAFKA_CONNECT_RETRIES: int = int(os.environ.get("KAFKA_CONNECT_RETRIES", "5"))
KAFKA_CONNECT_RETRY_DELAY: float = float(os.environ.get("KAFKA_CONNECT_RETRY_DELAY", "3.0"))

JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "15"))

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_AI_PROVIDER: str = os.environ.get("DEFAULT_AI_PROVIDER", "anthropic")

OTEL_EXPORTER_OTLP_ENDPOINT: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "stud-backend")
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS: List[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ── guard against wildcard CORS in production ─────────────────────────────────
if APP_ENV == "production" and ("*" in CORS_ORIGINS or not CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS must be explicitly set (no wildcards) in production")

RATE_LIMIT_PER_MINUTE: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))
MAX_UPLOAD_BYTES: int = int(os.environ.get("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))  # 100 MB
