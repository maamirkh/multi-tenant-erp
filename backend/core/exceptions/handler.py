"""Global FastAPI exception handlers.

Three handlers cover the entire exception surface:

1. ``application_exception_handler`` — catches ``ApplicationException`` and
   its subclasses (NotFoundException, ConflictException, …).  Returns a
   typed ``ErrorResponse`` with the exception's ``code``, ``message``, and
   ``details``.

2. ``validation_exception_handler`` — catches Pydantic ``RequestValidationError``
   (schema-level input validation) and normalises it to the same
   ``ErrorResponse`` format so clients see a consistent error envelope.

3. ``unhandled_exception_handler`` — catches every other ``Exception``.  Logs
   the full stack trace at ERROR level and returns a generic HTTP 500 body.
   Internal details are NEVER returned to clients in non-development
   environments.

Registration (in ``main.py``)::

    app.add_exception_handler(ApplicationException, application_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.exceptions.base import ApplicationException
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _build_error_json(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialise an ``ErrorResponse`` to a plain dict for ``JSONResponse``."""
    return ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
        )
    ).model_dump()


async def application_exception_handler(
    request: Request,
    exc: ApplicationException,
) -> JSONResponse:
    """Handle all ``ApplicationException`` subclasses.

    Logs at WARNING for client errors (4xx) and ERROR for server errors (5xx).
    The ``request_id`` from the context var is attached to every log record
    automatically via the structured logging formatter from Phase 2.
    """
    request_id = REQUEST_ID_CONTEXT.get("-")
    log_extra: dict[str, object] = {
        "request_id": request_id,
        "error_code": exc.code,
        "http_status": exc.http_status,
        "path": request.url.path,
    }

    if exc.http_status >= 500:
        logger.error(exc.message, extra=log_extra)
    else:
        logger.warning(exc.message, extra=log_extra)

    return JSONResponse(
        status_code=exc.http_status,
        content=_build_error_json(
            code=exc.code,
            message=exc.message,
            details=dict(exc.details),
        ),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Normalise Pydantic ``RequestValidationError`` to ``ErrorResponse`` format.

    Extracts per-field error detail from the Pydantic error list so API
    clients receive structured field-level feedback in the ``details`` map.

    Example ``details``::

        {
          "body.email": "value is not a valid email address",
          "body.quantity": "ensure this value is greater than 0"
        }
    """
    request_id = REQUEST_ID_CONTEXT.get("-")

    field_errors: dict[str, Any] = {}
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []))
        field_errors[loc] = error.get("msg", "Invalid value.")

    logger.warning(
        "Request validation failed",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "error_count": len(field_errors),
        },
    )

    return JSONResponse(
        status_code=422,
        content=_build_error_json(
            code="VALIDATION_ERROR",
            message="Request validation failed. Please check the submitted data.",
            details=field_errors,
        ),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Logs the full stack trace at ERROR level for operational visibility.
    Returns a generic HTTP 500 response — stack traces and internal details
    are NEVER sent to the client.

    The ``request.app.state.settings.ENVIRONMENT`` value is used to decide
    whether to include a slightly more verbose message in development.
    """
    request_id = REQUEST_ID_CONTEXT.get("-")

    logger.error(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "exc_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # Determine if we are in a development environment.
    # Use getattr with a safe default so this handler never raises itself.
    environment: str = getattr(
        getattr(request.app.state, "settings", None),
        "ENVIRONMENT",
        "production",
    )

    if environment == "development":
        # In development, include the exception type to speed up debugging.
        # The full traceback is in the logs; we give a minimal hint here.
        message = f"Internal server error: {type(exc).__name__}"
        details: dict[str, Any] = {"traceback": traceback.format_exc()}
    else:
        message = "An unexpected error occurred. Please try again later."
        details = {}

    return JSONResponse(
        status_code=500,
        content=_build_error_json(
            code="INTERNAL_ERROR",
            message=message,
            details=details,
        ),
        headers={"X-Request-ID": request_id},
    )
