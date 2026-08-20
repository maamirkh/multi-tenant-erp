"""Platform Administration module domain exceptions.

All exceptions inherit from ``ApplicationException`` (directly or via a
typed subclass) so the global FastAPI exception handler converts them to
typed ``ErrorResponse`` JSON automatically (Constitution §21) — same
convention as ``modules/accounting/exceptions.py``.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure
Python.
"""

from __future__ import annotations

from core.exceptions.base import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)


class PlatformSessionInvalidError(UnauthorizedException):
    """Raised when a Platform session is missing, expired, or revoked."""

    def __init__(
        self,
        message: str = "Platform session is invalid or has expired.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "PLATFORM_SESSION_INVALID"


class InsufficientPlatformPermissionError(ForbiddenException):
    """Raised when the authenticated Platform Administrator lacks a
    required permission code (plan.md §8 — genuinely enforced, not a stub)."""

    def __init__(
        self,
        message: str = "You do not hold the required Platform permission.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "INSUFFICIENT_PLATFORM_PERMISSION"


class CapabilityNotEntitledError(ForbiddenException):
    """Raised when a tenant's effective Plan entitlement denies a capability
    (plan.md §13.1 — point-of-use enforcement)."""

    def __init__(
        self,
        message: str = "This capability is not entitled under the current plan.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "CAPABILITY_NOT_ENTITLED"


class SupportAccessExpiredError(ForbiddenException):
    """Raised when a support-access grant has expired or been terminated
    (plan.md §21 — time-bounded, inspection-only)."""

    def __init__(
        self,
        message: str = "This support-access grant has expired or ended.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "SUPPORT_ACCESS_EXPIRED"


class LastPlatformOwnerError(ConflictException):
    """Raised when an operation would remove/deactivate the final active
    ``platform_owner``-role administrator (plan.md §8/§26 — service-level
    check; not expressible as a single-row DB constraint)."""

    def __init__(
        self,
        message: str = "Cannot remove or deactivate the last active Platform Owner.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "LAST_PLATFORM_OWNER"


class TenantLifecycleTransitionError(ConflictException):
    """Raised when a tenant lifecycle transition is not permitted from the
    tenant's current status (e.g. suspending an already-suspended tenant,
    Edge Cases #1/#2)."""

    def __init__(
        self,
        message: str = "This tenant lifecycle transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "TENANT_LIFECYCLE_TRANSITION_ERROR"
