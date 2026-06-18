"""Structured JSON logging for production.

Usage:
    from app.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("repo.created", extra={"repo": "alice/myrepo", "user_id": 1})

    # Or use the StructLogger wrapper for keyword convenience:
    log = StructLogger(__name__)
    log.info("repo.created", repo="alice/myrepo", user_id=1)
"""
import json
import logging
import sys
import time
from typing import Any

from .config import LOG_LEVEL, OTEL_SERVICE_NAME


class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    # keys stdlib adds to LogRecord that we don't want in the output
    _SKIP = frozenset((
        "args", "asctime", "created", "exc_info", "exc_text",
        "filename", "funcName", "id", "levelname", "levelno",
        "lineno", "message", "module", "msecs", "msg", "name",
        "pathname", "process", "processName", "relativeCreated",
        "stack_info", "thread", "threadName", "taskName",
    ))

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": OTEL_SERVICE_NAME,
        }
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        # attach any extra fields passed via extra={...}
        for key, val in record.__dict__.items():
            if key not in self._SKIP:
                base[key] = val
        return json.dumps(base, default=str)


def configure_logging() -> None:
    """Call once at application startup."""
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class StructLogger:
    """Convenience wrapper that accepts keyword args and forwards them as extra."""

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(self, level: int, msg: str, **kwargs: Any) -> None:
        self._log.log(level, msg, extra=kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self._emit(logging.CRITICAL, msg, **kwargs)
