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
    ValidationException,
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


class SelfEscalationError(ForbiddenException):
    """Raised when an actor attempts to grant the ``platform_owner`` role
    without already holding it themselves (BR-9A-012) — a role can never
    grant a role of equal-or-higher privilege the actor doesn't already
    have. Added in Phase 5 (T065); extends this module's exception
    catalogue the same way T033's permission catalogue was extended in
    Phase 5 for the RBAC seed service."""

    def __init__(
        self,
        message: str = "Cannot grant a role you do not already hold.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "SELF_ESCALATION_REJECTED"


class PlatformAdministratorAlreadyExistsError(ConflictException):
    """Raised when creating a Platform Administrator for a ``user_id`` that
    already has one (T068 — the DB carries a matching unique constraint;
    this gives a clean 409 instead of a raw ``IntegrityError``)."""

    def __init__(
        self,
        message: str = "A Platform Administrator already exists for this user.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "PLATFORM_ADMINISTRATOR_ALREADY_EXISTS"


class UnknownPlatformPermissionError(ValidationException):
    """Raised when a role's permission bundle references a code that does
    not exist in ``PLATFORM_PERMISSION_CODES`` (T033/T069) — permissions
    are configuration data, but a role can never be granted a code that
    isn't in the seeded catalogue."""

    def __init__(
        self,
        message: str = "One or more permission codes are not recognised.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "UNKNOWN_PLATFORM_PERMISSION"


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


class PlanTransitionError(ConflictException):
    """Raised when a Plan status transition is not permitted from its
    current status (e.g. retiring a draft Plan, publishing an
    already-published one, T111)."""

    def __init__(
        self,
        message: str = "This Plan status transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "PLAN_TRANSITION_ERROR"


class PlanNotAssignableError(ConflictException):
    """Raised when a Subscription is assigned/changed to a Plan that is
    not currently ``published`` (BR-9A-018, FR-9A-152, T113). A
    ``retired`` Plan keeps every tenant already subscribed to it
    unchanged — this error blocks only the **new**-assignment path; it
    is never raised for a Plan's already-existing Subscriptions."""

    def __init__(
        self,
        message: str = "Only a published Plan may be assigned to a tenant.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "PLAN_NOT_ASSIGNABLE"


class SubscriptionUsageConflictError(ConflictException):
    """Raised when a subscription change would place a tenant's current
    usage above the target Plan's limits, and the request did not carry
    an explicit acknowledgement (FR-9A-165, T113)."""

    def __init__(
        self,
        message: str = (
            "This subscription change would place current usage above the "
            "target plan's limits. Resubmit with acknowledged=true to proceed."
        ),
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "SUBSCRIPTION_USAGE_CONFLICT"


class EntitlementOverrideAlreadyActiveError(ConflictException):
    """Raised when granting an entitlement override for a
    (company, capability_key) pair that already has one active — the DB
    carries a matching partial unique index (migration 059); this gives a
    clean 409 instead of a raw ``IntegrityError`` (T146)."""

    def __init__(
        self,
        message: str = (
            "An active entitlement override already exists for this "
            "tenant/capability. Revoke it before granting a new one."
        ),
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "ENTITLEMENT_OVERRIDE_ALREADY_ACTIVE"


class QuotaOverrideAlreadyActiveError(ConflictException):
    """Raised when granting a tenant quota override for a
    (company, quota_key) pair that already has one active — the DB
    carries a matching partial unique index (migration 059) (T149)."""

    def __init__(
        self,
        message: str = (
            "An active quota override already exists for this "
            "tenant/quota key. Revoke it before granting a new one."
        ),
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.code = "QUOTA_OVERRIDE_ALREADY_ACTIVE"
