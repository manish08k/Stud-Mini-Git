"""Central settings – loaded once, consumed everywhere.

All values are read from environment variables (or a .env file via
python-dotenv if installed). Hard-coded defaults are dev-safe only.
"""
import os
import sys
from pathlib import Path
from typing import List

# ── optional dotenv support ──────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass  # dotenv not installed – env vars must be set manually

# ── path helpers ─────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── core ─────────────────────────────────────────────────────────────────────
APP_ENV: str = os.environ.get("APP_ENV", "development")
DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ── storage ───────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get("STUD_SERVER_DATA", BACKEND_DIR / "data"))
REPOS_DIR = DATA_DIR / "repos"
DATABASE_PATH = DATA_DIR / "stud_server.db"
DATABASE_URL: str = os.environ.get("STUD_SERVER_DB_URL", f"sqlite:///{DATABASE_PATH}")

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)

# ── redis ─────────────────────────────────────────────────────────────────────
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── kafka ─────────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_EVENTS: str = os.environ.get("KAFKA_TOPIC_EVENTS", "stud.events")
KAFKA_CONSUMER_GROUP: str = os.environ.get("KAFKA_CONSUMER_GROUP", "stud-backend")
KAFKA_ENABLED: bool = os.environ.get("KAFKA_ENABLED", "false").lower() == "true"

# ── auth / JWT ────────────────────────────────────────────────────────────────
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

# ── AI providers ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_AI_PROVIDER: str = os.environ.get("DEFAULT_AI_PROVIDER", "anthropic")

# ── observability ─────────────────────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "stud-backend")
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# ── cors ──────────────────────────────────────────────────────────────────────
_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS: List[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ── rate limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))

# ── S3 / object storage ───────────────────────────────────────────────────────
S3_BUCKET: str = os.environ.get("S3_BUCKET", "")
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# ── GitHub Actions-compatible runner registration ─────────────────────────────
RUNNER_REGISTRATION_TOKEN_TTL: int = int(os.environ.get("RUNNER_REGISTRATION_TOKEN_TTL", "3600"))
