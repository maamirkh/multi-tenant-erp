"""Application exception hierarchy.

All exceptions raised by the DevSphere ERP business and infrastructure layers
inherit from ``ApplicationException``.  This single base class carries enough
context for the global exception handler to produce a consistent, typed
``ErrorResponse`` without any application-specific knowledge.

Design constraints:
  - No FastAPI, Starlette, or HTTP imports.  Exceptions are pure Python so
    they can be raised from services, repositories, and utilities without
    coupling those layers to the web framework.
  - HTTP status codes live on the exception class as a hint to the handler,
    not as a hard dependency on any HTTP library.
  - ``details`` accepts arbitrary structured context (field errors, conflict
    reasons, …) for programmatic consumption by API clients.  It is never
    surfaced raw in production responses.
"""

from __future__ import annotations


class ApplicationException(Exception):
    """Base class for all application-level exceptions.

    Args:
        message:     Human-readable description; safe to surface in responses.
        code:        Machine-readable error code used by API clients.
        details:     Optional structured context (field names, values, …).
        http_status: HTTP status code the global handler should use.
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"http_status={self.http_status})"
        )


class ValidationException(ApplicationException):
    """Raised when request input fails business-level validation.

    Distinct from Pydantic ``RequestValidationError``, which covers schema
    validation.  Use ``ValidationException`` when the input is structurally
    valid but violates a business rule (e.g. duplicate SKU, negative quantity).
    """

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            http_status=422,
        )


class NotFoundException(ApplicationException):
    """Raised when a requested resource does not exist or is not visible.

    Covers both "does not exist" and "exists but belongs to a different
    tenant" scenarios — both return 404 to avoid information disclosure.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details=details,
            http_status=404,
        )


class ConflictException(ApplicationException):
    """Raised when an operation conflicts with existing data.

    Examples: duplicate email, duplicate SKU, optimistic locking failure.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
            http_status=409,
        )


class UnauthorizedException(ApplicationException):
    """Raised when a request requires authentication but none is provided."""

    def __init__(
        self,
        message: str = "Authentication required.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            details=details,
            http_status=401,
        )


class ForbiddenException(ApplicationException):
    """Raised when an authenticated user lacks permission for an action."""

    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            details=details,
            http_status=403,
        )


class InfrastructureException(ApplicationException):
    """Raised when an external dependency (DB, cache, external API) fails.

    Always maps to HTTP 500.  The handler logs the full context but returns
    a generic message to the client so no infrastructure details are leaked.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            details=details,
            http_status=500,
        )
