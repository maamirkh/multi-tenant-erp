"""Companies module exception hierarchy.

All exceptions inherit ``ApplicationException`` from ``core.exceptions.base``
so the global FastAPI exception handler converts them to typed ``ErrorResponse``
JSON automatically.

Error codes match spec.md §12.2 exactly.  HTTP status codes follow RFC 9110:
  400 Bad Request, 403 Forbidden, 404 Not Found, 409 Conflict,
  410 Gone, 422 Unprocessable Entity.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure Python.
"""

from __future__ import annotations

from core.exceptions.base import ApplicationException

# ── 400 Bad Request ───────────────────────────────────────────────────────────


class LogoTooLargeError(ApplicationException):
    """Logo file exceeds the configured maximum size."""

    def __init__(
        self,
        message: str = "Logo file exceeds the maximum allowed size.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LOGO_TOO_LARGE",
            details=details,
            http_status=400,
        )


class LogoInvalidFormatError(ApplicationException):
    """Logo file has an unsupported MIME type or extension."""

    def __init__(
        self,
        message: str = "Unsupported logo file format.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LOGO_INVALID_FORMAT",
            details=details,
            http_status=400,
        )


class LogoInvalidContentError(ApplicationException):
    """Logo file's magic bytes do not match the declared content type."""

    def __init__(
        self,
        message: str = "Logo file content does not match its declared type.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LOGO_INVALID_CONTENT",
            details=details,
            http_status=400,
        )


# ── 403 Forbidden ─────────────────────────────────────────────────────────────


class CompanySuspendedError(ApplicationException):
    """Company is suspended; only a SuperAdmin can lift the suspension."""

    def __init__(
        self,
        message: str = "Company is suspended. Please contact support.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="COMPANY_SUSPENDED",
            details=details,
            http_status=403,
        )


# ── 404 Not Found ─────────────────────────────────────────────────────────────


class CompanyNotFoundError(ApplicationException):
    """Requested company does not exist, is deleted, or belongs to another tenant."""

    def __init__(
        self,
        message: str = "Company not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="COMPANY_NOT_FOUND",
            details=details,
            http_status=404,
        )


# ── 409 Conflict ──────────────────────────────────────────────────────────────


class CompanyNameConflictError(ApplicationException):
    """Legal name is already taken (case-insensitive global uniqueness)."""

    def __init__(
        self,
        message: str = "A company with this legal name already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="COMPANY_NAME_CONFLICT",
            details=details,
            http_status=409,
        )


class SlugConflictError(ApplicationException):
    """Requested slug is already taken by another company."""

    def __init__(
        self,
        message: str = "This slug is already in use.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SLUG_CONFLICT",
            details=details,
            http_status=409,
        )


class InvalidStatusTransitionError(ApplicationException):
    """Requested status change is not permitted from the current status."""

    def __init__(
        self,
        message: str = "This status transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_STATUS_TRANSITION",
            details=details,
            http_status=409,
        )


class ActiveSubscriptionError(ApplicationException):
    """Company cannot be deleted while an active subscription exists."""

    def __init__(
        self,
        message: str = "Cannot delete a company with an active subscription.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ACTIVE_SUBSCRIPTION",
            details=details,
            http_status=409,
        )


# ── 410 Gone ──────────────────────────────────────────────────────────────────


class CompanyPurgedError(ApplicationException):
    """Company was permanently deleted; data is unrecoverable."""

    def __init__(
        self,
        message: str = "Company data has been permanently deleted and cannot be recovered.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="COMPANY_PURGED",
            details=details,
            http_status=410,
        )


# ── 422 Unprocessable Entity ──────────────────────────────────────────────────


class CompanyIncompleteError(ApplicationException):
    """Company cannot be activated because required setup fields are missing.

    Args:
        missing_fields: List of field names that must be completed before activation.
    """

    def __init__(
        self,
        missing_fields: list[str],
        message: str = "Company setup is incomplete. Required fields are missing.",
        details: dict[str, object] | None = None,
    ) -> None:
        merged: dict[str, object] = {"missing_fields": missing_fields}
        if details:
            merged.update(details)
        super().__init__(
            message=message,
            code="COMPANY_INCOMPLETE",
            details=merged,
            http_status=422,
        )


class SlugImmutableError(ApplicationException):
    """Slug cannot be changed after the company has been activated."""

    def __init__(
        self,
        message: str = "Company slug cannot be changed after activation.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SLUG_IMMUTABLE",
            details=details,
            http_status=422,
        )


class ForceDeleteRequiredError(ApplicationException):
    """Active transactions exist; caller must pass ``force_delete=True`` to proceed."""

    def __init__(
        self,
        message: str = "Active transactions exist. Pass force_delete=true to confirm deletion.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="FORCE_DELETE_REQUIRED",
            details=details,
            http_status=422,
        )


class CurrencyChangeWarningError(ApplicationException):
    """Currency change detected with existing transactions; explicit confirmation required."""

    def __init__(
        self,
        message: str = (
            "Changing the default currency will not convert existing transactions. "
            "Pass confirm_currency_change=true to proceed."
        ),
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CURRENCY_CHANGE_WARNING",
            details=details,
            http_status=422,
        )
