"""Structured logging configuration for DevSphere ERP.

In production environments log records are serialised to JSON so that log
aggregation systems (e.g. Loki, CloudWatch, Datadog) can parse them without
extra configuration.

In development/non-production environments a human-readable coloured format
is used so developers can read logs directly in the terminal.

Usage::

    from core.logging.setup import configure_logging, REQUEST_ID_CONTEXT
    configure_logging(settings)

The ``REQUEST_ID_CONTEXT`` ContextVar is populated by ``RequestIDMiddleware``
and read by the log formatter so that every log line emitted during a request
carries the matching ``request_id`` field.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from core.config.settings import Settings

# ---------------------------------------------------------------------------
# Per-request context variables — populated by middleware for the full call stack.
# ---------------------------------------------------------------------------
REQUEST_ID_CONTEXT: ContextVar[str] = ContextVar("request_id", default="-")

# Populated by AuthHookMiddleware / get_current_user once the JWT is validated.
# Values are string representations of the UUIDs (or "-" when unauthenticated).
USER_ID_CONTEXT: ContextVar[str] = ContextVar("user_id", default="-")
SESSION_ID_CONTEXT: ContextVar[str] = ContextVar("session_id", default="-")


class _JSONFormatter(logging.Formatter):
    """Serialise log records to a single-line JSON object.

    Fields emitted:
      timestamp  — ISO 8601 UTC string
      level      — log level name (INFO, ERROR, …)
      logger     — logger name (dotted module path)
      message    — formatted log message
      request_id — value from REQUEST_ID_CONTEXT (populated by middleware)
      environment — value from the Settings instance passed at construction
    """

    def __init__(self, environment: str) -> None:
        super().__init__()
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": REQUEST_ID_CONTEXT.get("-"),
            "user_id": USER_ID_CONTEXT.get("-"),
            "session_id": SESSION_ID_CONTEXT.get("-"),
            "environment": self._environment,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _DevFormatter(logging.Formatter):
    """Human-readable formatter for development environments.

    Produces lines in the form::

        2026-07-11T10:00:00.000+00:00 | INFO | core.config.settings | message [req=id]
    """

    _LEVEL_COLOURS: dict[str, str] = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._LEVEL_COLOURS.get(record.levelname, "")
        reset = self._RESET
        timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
        level = f"{colour}{record.levelname:<8}{reset}"
        request_id = REQUEST_ID_CONTEXT.get("-")
        user_id = USER_ID_CONTEXT.get("-")
        session_id = SESSION_ID_CONTEXT.get("-")
        base = (
            f"{timestamp} | {level} | {record.name} | {record.getMessage()}"
            f" [req={request_id} user={user_id} sid={session_id}]"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(settings: Settings) -> None:
    """Configure the root Python logging handler.

    Must be called once at application startup, *before* the FastAPI instance
    is created, so that all subsequent log records (including SQLAlchemy and
    Uvicorn) pass through the configured formatter.

    Subsequent calls are idempotent — existing handlers are removed and
    replaced to avoid duplicate output.
    """
    root_logger = logging.getLogger()

    # Remove any pre-existing handlers to avoid duplicate log lines.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if settings.ENVIRONMENT == "production":
        handler.setFormatter(_JSONFormatter(environment=settings.ENVIRONMENT))
    else:
        handler.setFormatter(_DevFormatter())

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers in production.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
