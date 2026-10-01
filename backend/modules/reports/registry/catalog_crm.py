"""Report Registry entries for CRM's 4 "Now" reports (T103). Importing
this module registers every entry and populates
``ADAPTER_REGISTRY[ReportDomain.CRM]``.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.reports.registry.definitions import (
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.schemas.crm import (
    ActivityReportFilter,
    CrmDashboardFilter,
    LeadReportFilter,
    PipelineReportFilter,
)
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from modules.reports.services.adapters.crm_adapter import CrmAdapter

ADAPTER_REGISTRY[ReportDomain.CRM] = CrmAdapter()


def _crm_aggregate_report(
    *,
    key: str,
    name: str,
    description: str,
    authoritative_source: str,
    supported_filters: type[BaseModel],
) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        name=name,
        description=description,
        domain=ReportDomain.CRM,
        authoritative_source=authoritative_source,
        required_permission="reports.crm.view",
        export_permission=None,
        domain_capability_key="crm",
        supported_filters=supported_filters,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


register(
    _crm_aggregate_report(
        key="crm.pipeline",
        name="Pipeline Report",
        description="Opportunity value by stage/owner/source, win rate.",
        authoritative_source=(
            "modules.crm.services.reporting_service.CrmReportingService."
            "get_pipeline_report"
        ),
        supported_filters=PipelineReportFilter,
    )
)

register(
    _crm_aggregate_report(
        key="crm.leads",
        name="Lead Report",
        description="Lead volume, status/source breakdown, conversion rate.",
        authoritative_source=(
            "modules.crm.services.reporting_service.CrmReportingService.get_lead_report"
        ),
        supported_filters=LeadReportFilter,
    )
)

register(
    _crm_aggregate_report(
        key="crm.activities",
        name="Activity Report",
        description="Completed/overdue activity counts by type/owner.",
        authoritative_source=(
            "modules.crm.services.reporting_service.CrmReportingService."
            "get_activity_report"
        ),
        supported_filters=ActivityReportFilter,
    )
)

register(
    _crm_aggregate_report(
        key="crm.dashboard",
        name="CRM Dashboard",
        description="Current-month pipeline/lead/activity KPI snapshot.",
        authoritative_source=(
            "modules.crm.services.reporting_service.CrmReportingService.get_dashboard"
        ),
        supported_filters=CrmDashboardFilter,
    )
)
