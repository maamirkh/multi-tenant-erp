"""Report Registry entry for the Executive Dashboard (``exec.dashboard``,
T151, spec §13). ``execution_kind=COMPOSITE`` — resolved through
``COMPOSITE_REPORT_HANDLERS``, never ``ADAPTER_REGISTRY`` (Blocker A);
unreachable via the generic ``GET /{report_key}`` path (T126), served only
by its own dedicated ``GET /reports/dashboard`` route (T150).

Importing this module registers the entry and wires
``COMPOSITE_REPORT_HANDLERS["exec.dashboard"]`` to the exact same bound
method the dedicated route calls, so T032's identity check passes.
"""

from __future__ import annotations

from modules.reports.registry.definitions import (
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.schemas.dashboard import DashboardFilter
from modules.reports.services.adapters.base import COMPOSITE_REPORT_HANDLERS
from modules.reports.services.dashboard_service import get_dashboard

register(
    ReportDefinition(
        key="exec.dashboard",
        name="Executive Dashboard",
        description="Curated cross-module KPI overview (spec §10 metrics).",
        domain=ReportDomain.EXECUTIVE,
        authoritative_source=(
            "modules.reports.services.dashboard_service.get_dashboard"
        ),
        required_permission="reports.executive.view",
        export_permission=None,
        domain_capability_key=None,
        supported_filters=DashboardFilter,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.COMPOSITE,
    )
)

COMPOSITE_REPORT_HANDLERS["exec.dashboard"] = get_dashboard
