"""Report Registry entries for Purchase's 7 "Now" reports (T080).
Importing this module registers every entry and populates
``ADAPTER_REGISTRY[ReportDomain.PURCHASE]``.
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
from modules.reports.schemas.purchase import (
    OpenCommitmentsFilter,
    PendingDeliveriesFilter,
    PurchaseBySupplierFilter,
    PurchaseKpiFilter,
    PurchaseSummaryFilter,
    SupplierPerformanceFilter,
    VendorReturnsFilter,
)
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from modules.reports.services.adapters.purchase_adapter import PurchaseAdapter

ADAPTER_REGISTRY[ReportDomain.PURCHASE] = PurchaseAdapter()

_PO_DRILL_DOWN = (
    DrillDownTarget(
        label="View purchase order",
        target_route="/purchase-orders/{po_id}",
        required_permission="purchase.orders.read",
        preserves_filters=("supplier_id",),
    ),
)


def _purchase_list_report(
    *,
    key: str,
    name: str,
    description: str,
    authoritative_source: str,
    supported_filters: type[BaseModel],
    supported_dimensions: tuple[str, ...],
    supported_measures: tuple[str, ...],
    branch_filterable: bool = False,
) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        name=name,
        description=description,
        domain=ReportDomain.PURCHASE,
        authoritative_source=authoritative_source,
        required_permission="reports.purchase.view",
        export_permission="reports.purchase.export",
        domain_capability_key="purchase",
        supported_filters=supported_filters,
        supported_dimensions=supported_dimensions,
        supported_measures=supported_measures,
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=_PO_DRILL_DOWN,
        branch_filterable=branch_filterable,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


register(
    _purchase_list_report(
        # group-by cardinality: status (fixed set) x supplier (<= tenant suppliers); offset-paged
        key="purchase.summary",
        name="Purchase Summary",
        description="PO/spend overview.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService."
            "purchase_order_summary"
        ),
        supported_filters=PurchaseSummaryFilter,
        supported_dimensions=("status", "supplier"),
        supported_measures=("total",),
    )
)

register(
    _purchase_list_report(
        # group-by cardinality: one row per supplier (<= tenant suppliers); offset-paged
        key="purchase.by_supplier",
        name="Purchase by Supplier",
        description="Spend per supplier.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService.purchase_by_supplier"
        ),
        supported_filters=PurchaseBySupplierFilter,
        supported_dimensions=("supplier",),
        supported_measures=("total_spend",),
    )
)

register(
    _purchase_list_report(
        # group-by cardinality: one row per supplier (<= tenant suppliers); offset-paged
        key="purchase.supplier_performance",
        name="Supplier Performance",
        description="On-time %, rejection %, PPV.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService.supplier_performance"
        ),
        supported_filters=SupplierPerformanceFilter,
        supported_dimensions=("supplier",),
        supported_measures=("on_time_rate", "rejection_rate"),
    )
)

register(
    _purchase_list_report(
        # group-by cardinality: supplier (<= tenant suppliers), one row per open PO line; offset-paged
        key="purchase.open_commitments",
        name="Open Purchase Commitments",
        description="Outstanding PO value.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService."
            "open_purchase_commitments"
        ),
        supported_filters=OpenCommitmentsFilter,
        supported_dimensions=("supplier",),
        supported_measures=("open_value",),
        branch_filterable=True,
    )
)

register(
    _purchase_list_report(
        # group-by cardinality: supplier (<= tenant suppliers), one row per PO; offset-paged
        key="purchase.pending_deliveries",
        name="Pending / Overdue Deliveries",
        description="POs awaiting receipt.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService.overdue_deliveries"
        ),
        supported_filters=PendingDeliveriesFilter,
        supported_dimensions=("supplier",),
        supported_measures=("total",),
        branch_filterable=True,
    )
)

register(
    _purchase_list_report(
        # group-by cardinality: supplier (<= tenant suppliers), one row per RMA; offset-paged
        key="purchase.vendor_returns",
        name="Vendor Return Report",
        description="RMA activity.",
        authoritative_source=(
            "modules.purchase.services.report_service.ReportService.vendor_return_report"
        ),
        supported_filters=VendorReturnsFilter,
        supported_dimensions=("supplier",),
        supported_measures=(),
    )
)

register(
    ReportDefinition(
        key="purchase.kpis",
        name="Purchase KPI Dashboard",
        description="10 existing Purchase KPIs.",
        domain=ReportDomain.PURCHASE,
        authoritative_source=(
            "modules.purchase.services.kpi_service.KPIService.get_all_kpis"
        ),
        required_permission="reports.purchase.view",
        export_permission=None,
        domain_capability_key="purchase",
        supported_filters=PurchaseKpiFilter,
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
