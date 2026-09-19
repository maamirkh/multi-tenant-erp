"""Report Registry entries for the Cross-Module domain: the "Now"
Customer 360 composite (``crossmodule.customer_360``, T166, spec §20,
plan.md §14) and the one Deferred cross-module report,
``crossmodule.branch_performance`` (T123, spec §9/§25, FR-RPT-012/112).

Definitively Deferred (not merely "recommended Deferred", per the
2026-09-11 micro-correction pass resolving OQ-3): no Branch domain/ACL
exists and real, populated ``branch_id`` data is not established for any
known tenant today. Its only promotion prerequisite is `/sp.plan`
confirming, against real tenant data, that the underlying ``branch_id``
columns are actually populated for at least one representative tenant —
until then it MUST NOT ship as "Now".

``authoritative_source`` is a placeholder string — no real aggregation
source exists yet (spans Purchase/Inventory/Installments' own
branch-tagged entities, never a single existing method). T032 explicitly
exempts ``DEFERRED`` entries from the resolvability check, so this never
needs to resolve to a real callable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modules.reports.registry.definitions import (
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.services.adapters.base import COMPOSITE_REPORT_HANDLERS
from modules.reports.services.customer_360_service import get_customer_360


class BranchPerformanceFilter(BaseModel):
    """Placeholder filter shape — never exercised while Deferred."""

    model_config = ConfigDict(extra="forbid")


class Customer360Filter(BaseModel):
    """Registry-shape placeholder (T032 requires ``supported_filters`` be a
    ``BaseModel`` subclass for every entry, ``COMPOSITE`` included) —
    ``GET /reports/customer-360/{customer_id}`` (T165) never routes
    through the generic ``_authorize_and_validate()`` this would otherwise
    feed; ``customer_id`` is a path parameter, not a query filter."""

    model_config = ConfigDict(extra="forbid")


register(
    ReportDefinition(
        key="crossmodule.customer_360",
        name="Customer 360 Financial View",
        description=(
            "One customer's Sales activity + AR balance + CRM/Installment "
            "exposure in one authorized view."
        ),
        domain=ReportDomain.CROSSMODULE,
        authoritative_source=(
            "modules.reports.services.customer_360_service.get_customer_360"
        ),
        required_permission="reports.customer_360.view",
        export_permission="reports.customer_360.view",
        domain_capability_key=None,
        supported_filters=Customer360Filter,
        supported_dimensions=("customer",),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.COMPOSITE,
    )
)

COMPOSITE_REPORT_HANDLERS["crossmodule.customer_360"] = get_customer_360


register(
    ReportDefinition(
        key="crossmodule.branch_performance",
        name="Branch Performance Summary",
        description=(
            "Purchase/Inventory/Installments activity by the reserved "
            "branch_id column, where populated (deferred)."
        ),
        domain=ReportDomain.CROSSMODULE,
        authoritative_source="crossmodule.branch_performance.NOT_YET_IMPLEMENTED",
        required_permission="reports.branch_performance.view",
        export_permission=None,
        domain_capability_key=None,
        supported_filters=BranchPerformanceFilter,
        supported_dimensions=("branch", "period"),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(),
        drill_down_targets=(),
        branch_filterable=True,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.DEFERRED,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)
