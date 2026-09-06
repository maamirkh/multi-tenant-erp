"""CRM module domain exceptions.

All exceptions inherit from ``ApplicationException`` via the module-level
``CrmException`` base so the global FastAPI exception handler converts them
to typed ``ErrorResponse`` JSON automatically — zero new exception-handler
registration required, matching the Accounting/Inventory/Sales convention.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure
Python.

Spec ref: specs/009-crm/spec.md §38.7 (Error Responses), §14.3/§17.3/§19.2
(validation rules), §16 (Lead Conversion).
"""

from __future__ import annotations

from core.exceptions.base import (
    ApplicationException,
    ConflictException,
    NotFoundException,
)


class CrmException(ApplicationException):
    """Base exception for all CRM module errors."""

    def __init__(
        self,
        message: str,
        code: str = "CRM_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(
            message=message, code=code, details=details, http_status=http_status
        )


# ── Not Found (404) ─────────────────────────────────────────────────────────


class LeadNotFoundError(NotFoundException):
    """Raised when a referenced Lead does not exist for this company."""

    def __init__(self, lead_id: str | None = None) -> None:
        super().__init__(
            message=f"Lead '{lead_id}' not found.",
            details={"lead_id": lead_id},
        )


class OpportunityNotFoundError(NotFoundException):
    """Raised when a referenced Opportunity does not exist for this company."""

    def __init__(self, opportunity_id: str | None = None) -> None:
        super().__init__(
            message=f"Opportunity '{opportunity_id}' not found.",
            details={"opportunity_id": opportunity_id},
        )


class ActivityNotFoundError(NotFoundException):
    """Raised when a referenced Activity does not exist for this company."""

    def __init__(self, activity_id: str | None = None) -> None:
        super().__init__(
            message=f"Activity '{activity_id}' not found.",
            details={"activity_id": activity_id},
        )


class PipelineNotFoundError(NotFoundException):
    """Raised when a referenced Pipeline (or PipelineStage) does not exist
    for this company."""

    def __init__(self, pipeline_id: str | None = None) -> None:
        super().__init__(
            message=f"Pipeline '{pipeline_id}' not found.",
            details={"pipeline_id": pipeline_id},
        )


class LeadSourceNotFoundError(NotFoundException):
    """Raised when a referenced LeadSource does not exist for this company."""

    def __init__(self, source_id: str | None = None) -> None:
        super().__init__(
            message=f"Lead source '{source_id}' not found.",
            details={"source_id": source_id},
        )


class CustomerNotFoundError(NotFoundException):
    """Raised when Customer 360 (spec.md §20) is requested for a Sales
    ``customer_id`` that does not exist, or does not belong to this
    company (§30.2 cross-tenant 404 convention) — checked before any other
    Customer 360 query runs."""

    def __init__(self, customer_id: str | None = None) -> None:
        super().__init__(
            message=f"Customer '{customer_id}' not found.",
            details={"customer_id": customer_id},
        )


# ── Conflict (409) ───────────────────────────────────────────────────────────


class InvalidLeadTransitionError(ConflictException):
    """Raised when a Lead status transition is not permitted by spec.md §14.2."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            message=(
                f"Invalid Lead status transition: {current_status!r} -> "
                f"{target_status!r}."
            ),
            details={"current_status": current_status, "target_status": target_status},
        )


class InvalidOpportunityTransitionError(ConflictException):
    """Raised when an Opportunity status transition is not permitted by
    spec.md §17.2, or when a stage/value change is attempted on a terminal
    (``WON``/``LOST``) Opportunity."""

    def __init__(self, current_status: str, target_status: str | None = None) -> None:
        message = (
            f"Invalid Opportunity status transition: {current_status!r} -> "
            f"{target_status!r}."
            if target_status is not None
            else f"Opportunity is {current_status!r} and cannot be modified further."
        )
        super().__init__(
            message=message,
            details={"current_status": current_status, "target_status": target_status},
        )


class LeadNotQualifiedError(ConflictException):
    """Raised when conversion is attempted on a Lead that is not
    ``QUALIFIED`` (spec.md §16.1) and is not already ``CONVERTED``
    (the idempotent no-op case, handled separately, not via this
    exception)."""

    def __init__(self, lead_id: str, current_status: str) -> None:
        super().__init__(
            message=(
                f"Lead '{lead_id}' is not QUALIFIED (current status: "
                f"{current_status!r}) and cannot be converted."
            ),
            details={"lead_id": lead_id, "current_status": current_status},
        )


class PipelineStageInUseError(ConflictException):
    """Raised when deactivating a PipelineStage that still has OPEN
    Opportunities positioned on it (spec.md §17.2/plan.md BR-007)."""

    def __init__(self, stage_id: str, open_opportunity_count: int) -> None:
        super().__init__(
            message=(
                f"Pipeline stage '{stage_id}' cannot be deactivated: "
                f"{open_opportunity_count} open opportunity(ies) are on it."
            ),
            details={
                "stage_id": stage_id,
                "open_opportunity_count": open_opportunity_count,
            },
        )


# ── Feature Flag / Permission (403) ─────────────────────────────────────────


class CrmFeatureDisabledError(CrmException):
    """Raised when a CRM endpoint is called while ``feature.crm.enabled`` is
    disabled for the company. Mirrors the exact convention already
    established by ``InventoryFeatureDisabledError``/
    ``AccountingFeatureDisabledError`` — a dedicated ``FEATURE_DISABLED``
    / 403 rather than a generic 4xx.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or "The CRM module is not enabled for this company.",
            code="FEATURE_DISABLED",
            details={"feature_key": "feature.crm.enabled"},
            http_status=403,
        )


class CrmPermissionDeniedError(CrmException):
    """Raised when the authenticated user lacks the required CRM permission
    for the requested action (wired in Phase 8, per plan.md §17.3)."""

    def __init__(self, permission_code: str) -> None:
        super().__init__(
            message=f"You do not have the '{permission_code}' permission.",
            code="FORBIDDEN",
            details={"permission_code": permission_code},
            http_status=403,
        )
