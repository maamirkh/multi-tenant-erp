"""Report Registry entries for Installments' 7 "Now" reports (T114).
Importing this module registers every entry and populates
``ADAPTER_REGISTRY[ReportDomain.INSTALLMENTS]``.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.reports.registry.definitions import (
    DrillDownTarget,
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.schemas.installments import (
    CollectionsFilter,
    ContractRegisterFilter,
    DueOverdueFilter,
    InstallmentAgingFilter,
    InstallmentDashboardFilter,
    PlanPerformanceFilter,
    SettlementWriteoffFilter,
)
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter

ADAPTER_REGISTRY[ReportDomain.INSTALLMENTS] = InstallmentsAdapter()

_CONTRACT_DRILL_DOWN = (
    DrillDownTarget(
        label="View contract",
        target_route="/installments/contracts/{contract_id}",
        required_permission="installments.contracts.read",
        preserves_filters=(),
    ),
)


def _installments_list_report(
    *,
    key: str,
    name: str,
    description: str,
    authoritative_source: str,
    supported_filters: type[BaseModel],
    supported_dimensions: tuple[str, ...],
    supported_measures: tuple[str, ...],
) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        name=name,
        description=description,
        domain=ReportDomain.INSTALLMENTS,
        authoritative_source=authoritative_source,
        required_permission="reports.installments.view",
        export_permission="reports.installments.export",
        domain_capability_key="installments",
        supported_filters=supported_filters,
        supported_dimensions=supported_dimensions,
        supported_measures=supported_measures,
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=_CONTRACT_DRILL_DOWN,
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


register(
    _installments_list_report(
        # group-by cardinality: status (8 fixed values) x customer (<= tenant customers); offset-paged
        key="installments.register",
        name="Installment Contract Register",
        description="Full contract listing.",
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_contract_register"
        ),
        supported_filters=ContractRegisterFilter,
        supported_dimensions=("status", "customer"),
        supported_measures=("count", "outstanding"),
    )
)

register(
    _installments_list_report(
        # group-by cardinality: period = bounded date range; offset-paged
        key="installments.collections",
        name="Installment Collection Report",
        description="Payments collected.",
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_collection_report"
        ),
        supported_filters=CollectionsFilter,
        supported_dimensions=("period",),
        supported_measures=("collected_amount",),
    )
)

register(
    _installments_list_report(
        # group-by cardinality: single as_of_date; population capped at 50,000; offset-paged
        key="installments.due_overdue",
        name="Due / Overdue Report",
        description="Upcoming/overdue installments.",
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_due_report"
        ),
        supported_filters=DueOverdueFilter,
        supported_dimensions=("as_of_date",),
        supported_measures=("due_amount", "overdue_amount"),
    )
)

register(
    _installments_list_report(
        # group-by cardinality: single as_of_date, fixed buckets; population capped at 50,000; offset-paged
        key="installments.aging",
        name="Installment Aging",
        description="Delinquency buckets.",
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_aging_report"
        ),
        supported_filters=InstallmentAgingFilter,
        supported_dimensions=("as_of_date",),
        supported_measures=("aging_buckets",),
    )
)

register(
    _installments_list_report(
        # group-by cardinality: period x status (fixed set); population capped at 50,000; offset-paged
        key="installments.settlement_writeoff",
        name="Settlement / Default / Write-off Report",
        description="Early payoff, default, write-off activity.",
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_settlement_report"
        ),
        supported_filters=SettlementWriteoffFilter,
        supported_dimensions=("period", "status"),
        supported_measures=("settled_value", "written_off_value"),
    )
)

register(
    ReportDefinition(
        # group-by cardinality: one row per plan template (typically tens); one aggregate
        key="installments.plan_performance",
        name="Plan/Template Performance",
        description="Adoption by plan template.",
        domain=ReportDomain.INSTALLMENTS,
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_plan_performance_report"
        ),
        required_permission="reports.installments.view",
        export_permission="reports.installments.export",
        domain_capability_key="installments",
        supported_filters=PlanPerformanceFilter,
        supported_dimensions=("plan_template",),
        supported_measures=("contract_count", "total_contractual_amount"),
        sortable_fields=(),
        export_formats=(),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="installments.dashboard",
        name="Installment Dashboard",
        description="Existing 13-metric dashboard.",
        domain=ReportDomain.INSTALLMENTS,
        authoritative_source=(
            "modules.installments.services.reporting_service."
            "InstallmentReportingService.get_dashboard"
        ),
        required_permission="reports.installments.view",
        export_permission=None,
        domain_capability_key="installments",
        supported_filters=InstallmentDashboardFilter,
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
)
