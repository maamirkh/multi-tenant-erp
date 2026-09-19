"""Reports & Analytics module domain exceptions.

All ten typed exceptions the Reports execution/export/saved-view contract
raises (plan.md §21/§22/§26), each mapped to the exact
``(code, http_status)`` pair in plan.md's error table (§26, lines 858-867).
Every exception inherits from the module-level ``ReportsException`` base
(itself an ``ApplicationException``) so the global FastAPI exception
handler converts it to a typed ``ErrorResponse`` automatically — zero new
exception-handler registration required, matching the
Accounting/CRM/Inventory/Sales/Purchase/Installments convention.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure
Python.

Spec ref: specs/011-reports-analytics/plan.md §21/§22/§26.
"""

from __future__ import annotations

from core.exceptions.base import ApplicationException


class ReportsException(ApplicationException):
    """Base exception for all Reports module errors."""

    def __init__(
        self,
        message: str,
        code: str = "REPORTS_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(
            message=message, code=code, details=details, http_status=http_status
        )


class ReportNotFoundError(ReportsException):
    """The requested ``report_key`` does not exist in the Report Registry,
    or is registered with ``status=DEFERRED`` (FR-RPT-011). Both cases
    return the identical error — a deferred key must look identical to an
    unregistered one, preventing catalog-enumeration probing."""

    def __init__(self, report_key: str) -> None:
        super().__init__(
            message=f"Report '{report_key}' was not found.",
            code="REPORT_NOT_FOUND",
            details={"report_key": report_key},
            http_status=404,
        )


class ReportNotEntitledError(ReportsException):
    """The report's source domain (or ``reports`` itself) is not entitled
    for this company (plan.md §9 step 2)."""

    def __init__(self, domain_capability_key: str) -> None:
        super().__init__(
            message=(
                f"The '{domain_capability_key}' module is not entitled for "
                "this company."
            ),
            code="REPORT_NOT_ENTITLED",
            details={"domain_capability_key": domain_capability_key},
            http_status=403,
        )


class ReportPermissionDeniedError(ReportsException):
    """The authenticated user lacks the required ``reports.*`` permission
    code for this report (plan.md §9 step 3)."""

    def __init__(self, permission_code: str) -> None:
        super().__init__(
            message=f"Permission '{permission_code}' is required.",
            code="REPORT_PERMISSION_DENIED",
            details={"permission_code": permission_code},
            http_status=403,
        )


class FilterValidationError(ReportsException):
    """A filter payload failed the report's declared ``supported_filters``
    schema (unknown field, wrong type) — Pydantic ``extra="forbid"``
    rejection (FR-RPT-120)."""

    def __init__(self, report_key: str, detail: str) -> None:
        super().__init__(
            message=f"Invalid filters for report '{report_key}': {detail}",
            code="REPORT_INVALID_FILTER",
            details={"report_key": report_key, "detail": detail},
            http_status=422,
        )


class UnsupportedSortFieldError(ReportsException):
    """The requested ``sort`` field is not in the report's declared
    ``sortable_fields`` allow-list (FR-RPT-123)."""

    def __init__(self, report_key: str, sort_field: str) -> None:
        super().__init__(
            message=(
                f"Field '{sort_field}' is not sortable for report '{report_key}'."
            ),
            code="REPORT_UNSUPPORTED_SORT",
            details={"report_key": report_key, "sort_field": sort_field},
            http_status=422,
        )


class UnavailablePrerequisiteError(ReportsException):
    """A wrapped domain service raised its own documented "not yet
    configured" condition (e.g. Accounting with no COA yet) — re-raised as
    this typed exception rather than an unhandled 500 (FR-RPT-272,
    FR-RPT-341). Also the sole trigger for a dashboard widget becoming
    ``UNAVAILABLE`` rather than ``OMITTED`` or a propagated 5xx."""

    def __init__(self, report_key: str, reason: str) -> None:
        super().__init__(
            message=f"Report '{report_key}' is currently unavailable: {reason}",
            code="REPORT_UNAVAILABLE",
            details={"report_key": report_key, "reason": reason},
            http_status=409,
        )


class ExportTooLargeError(ReportsException):
    """The bounded row count for an export exceeds the report format's row
    limit (§30) — rejected before any row retrieval."""

    def __init__(self, report_key: str, count: int, limit: int) -> None:
        super().__init__(
            message=(
                f"Export for '{report_key}' has {count} rows, exceeding "
                f"the limit of {limit}."
            ),
            code="EXPORT_TOO_LARGE",
            details={"report_key": report_key, "count": count, "limit": limit},
            http_status=422,
        )


class SavedViewNotFoundError(ReportsException):
    """No ``SavedReportView`` row matches this ``(company_id, user_id,
    view_id)`` — identical whether the row never existed, was
    soft-deleted, or belongs to another user/tenant (no ownership- or
    existence-probing signal, plan.md §15)."""

    def __init__(self, view_id: str) -> None:
        super().__init__(
            message=f"Saved report view '{view_id}' was not found.",
            code="SAVED_VIEW_NOT_FOUND",
            details={"view_id": view_id},
            http_status=404,
        )


class RetiredReportKeyError(ReportsException):
    """A saved view's stored ``report_key`` no longer resolves to a
    ``status=NOW`` Report Registry entry at load time (plan.md §15 load-
    time reauthorization)."""

    def __init__(self, report_key: str) -> None:
        super().__init__(
            message=f"Report '{report_key}' is no longer available.",
            code="SAVED_VIEW_REPORT_RETIRED",
            details={"report_key": report_key},
            http_status=410,
        )


class ExportAuditPersistenceError(ReportsException):
    """The export audit record could not be durably committed — treated as
    a full export failure (§21.8/§26): the generated file bytes are
    discarded and never delivered to the caller. An infrastructure
    failure, not a client error."""

    def __init__(self, report_key: str) -> None:
        super().__init__(
            message=(
                f"Export for '{report_key}' could not be recorded and was "
                "not delivered."
            ),
            code="EXPORT_AUDIT_FAILED",
            details={"report_key": report_key},
            http_status=500,
        )
