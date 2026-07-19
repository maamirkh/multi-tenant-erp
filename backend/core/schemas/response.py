"""Standard API response schemas.

Every API endpoint in DevSphere ERP returns one of:
  - ``StandardResponse[T]``  — successful single-item or action response
  - ``ErrorResponse``        — any error condition (4xx / 5xx)

Both envelope types include ``ResponseMeta`` (request_id + timestamp) so
that every response can be correlated with a specific log entry.

Usage::

    from core.schemas.response import StandardResponse, ResponseMeta
    from core.utils.datetime import utcnow

    meta = ResponseMeta(request_id=..., timestamp=utcnow())
    return StandardResponse[UserOut](data=user, message="User retrieved.", meta=meta)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata attached to every API response for observability.

    Fields:
        request_id: Correlates the response to a specific log entry and to
                    the ``X-Request-ID`` response header.
        timestamp:  UTC datetime when the response was generated.
    """

    model_config = ConfigDict(from_attributes=True)

    request_id: str
    timestamp: datetime


class StandardResponse(BaseModel, Generic[T]):
    """Envelope for successful API responses.

    Type parameter ``T`` is the payload type (e.g. ``UserOut``, ``ProductOut``).

    Example JSON::

        {
          "data": { ... },
          "message": "User retrieved successfully.",
          "meta": { "request_id": "...", "timestamp": "..." }
        }
    """

    model_config = ConfigDict(from_attributes=True)

    data: T
    message: str
    meta: ResponseMeta


class ErrorDetail(BaseModel):
    """Structured error payload embedded inside ``ErrorResponse``.

    Fields:
        code:    Machine-readable error code (e.g. ``NOT_FOUND``, ``CONFLICT``).
        message: Human-readable description; safe to display in UI.
        details: Optional structured context for programmatic clients
                 (e.g. field-level validation errors).  Never contains
                 stack traces, secrets, or raw infrastructure messages.
    """

    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    """Envelope for all error API responses (4xx / 5xx).

    Example JSON::

        {
          "error": {
            "code": "NOT_FOUND",
            "message": "Product not found.",
            "details": {}
          }
        }

    Note: ``ErrorResponse`` intentionally does NOT include ``meta`` at the
    top level.  The ``request_id`` is carried in the ``X-Request-ID``
    response header and in the application logs; returning it inside the
    error body would be redundant for most error scenarios.
    """

    model_config = ConfigDict(from_attributes=True)

    error: ErrorDetail
