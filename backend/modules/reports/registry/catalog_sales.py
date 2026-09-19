"""Report Registry entries for Sales' 8 "Now" reports (T069). Importing
this module registers every entry and populates
``ADAPTER_REGISTRY[ReportDomain.SALES]``.
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
from modules.reports.schemas.sales import (
    QuotationPipelineFilter,
    SalesByCustomerFilter,
    SalesByProductFilter,
    SalesKpiFilter,
    SalesReturnsFilter,
    SalesSummaryFilter,
    SalesTrendFilter,
    TopCustomersFilter,
)
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from modules.reports.services.adapters.sales_adapter import SalesAdapter

ADAPTER_REGISTRY[ReportDomain.SALES] = SalesAdapter()

_INVOICE_DRILL_DOWN = (
    DrillDownTarget(
        label="View invoices",
        target_route="/sales/invoices",
        required_permission="sales.invoices.read",
        preserves_filters=("date_from", "date_to"),
    ),
)


def _sales_list_report(
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
        domain=ReportDomain.SALES,
        authoritative_source=authoritative_source,
        required_permission="reports.sales.view",
        export_permission="reports.sales.export",
        domain_capability_key="sales",
        supported_filters=supported_filters,
        supported_dimensions=supported_dimensions,
        supported_measures=supported_measures,
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=_INVOICE_DRILL_DOWN,
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


register(
    _sales_list_report(
        key="sales.summary",
        name="Sales Summary",
        description="Orders/invoices/revenue overview.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._sales_summary"
        ),
        supported_filters=SalesSummaryFilter,
        supported_dimensions=("date",),
        supported_measures=("revenue", "invoice_count"),
    )
)

register(
    _sales_list_report(
        key="sales.by_customer",
        name="Sales by Customer",
        description="Revenue/volume per customer.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._sales_by_customer"
        ),
        supported_filters=SalesByCustomerFilter,
        supported_dimensions=("customer",),
        supported_measures=("revenue", "invoice_count"),
    )
)

register(
    _sales_list_report(
        key="sales.by_product",
        name="Sales by Product",
        description="Revenue/volume per product.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._sales_by_product"
        ),
        supported_filters=SalesByProductFilter,
        supported_dimensions=("product",),
        supported_measures=("revenue", "total_qty"),
    )
)

register(
    _sales_list_report(
        key="sales.top_customers",
        name="Top Customers",
        description="Ranked customer value.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._sales_by_customer"
        ),
        supported_filters=TopCustomersFilter,
        supported_dimensions=("customer",),
        supported_measures=("revenue",),
    )
)

register(
    _sales_list_report(
        key="sales.trend",
        name="Sales Trend",
        description="Period-over-period trend.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._sales_summary"
        ),
        supported_filters=SalesTrendFilter,
        supported_dimensions=("date",),
        supported_measures=("revenue",),
    )
)

register(
    _sales_list_report(
        key="sales.quotation_pipeline",
        name="Quotation Pipeline / Conversion",
        description="Quote-to-order funnel.",
        authoritative_source=(
            "modules.sales.services.report_service.ReportService._quotation_pipeline"
        ),
        supported_filters=QuotationPipelineFilter,
        supported_dimensions=("status",),
        supported_measures=("total_amount",),
    )
)

register(
    _sales_list_report(
        key="sales.returns",
        name="Sales Returns",
        description="Return/credit-note activity.",
        authoritative_source=(
            "modules.sales.services.return_service.ReturnService.list_returns"
        ),
        supported_filters=SalesReturnsFilter,
        supported_dimensions=("status",),
        supported_measures=(),
    )
)

register(
    ReportDefinition(
        key="sales.kpis",
        name="Sales KPI Dashboard",
        description="12 existing Sales KPIs.",
        domain=ReportDomain.SALES,
        authoritative_source="modules.sales.services.kpi_service.KPIService.get_dashboard",
        required_permission="reports.sales.view",
        export_permission=None,
        domain_capability_key="sales",
        supported_filters=SalesKpiFilter,
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
