"""Report Registry entries for Inventory's 8 "Now" reports (T093).
Importing this module registers every entry and populates
``ADAPTER_REGISTRY[ReportDomain.INVENTORY]``.
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
from modules.reports.schemas.inventory import (
    DeadStockFilter,
    InventoryKpiFilter,
    InventorySummaryFilter,
    InventoryValuationFilter,
    LowStockFilter,
    MovementVelocityFilter,
    StockAgingFilter,
    StockPositionFilter,
)
from modules.reports.services.adapters.base import ADAPTER_REGISTRY
from modules.reports.services.adapters.inventory_adapter import InventoryAdapter

ADAPTER_REGISTRY[ReportDomain.INVENTORY] = InventoryAdapter()

_PRODUCT_DRILL_DOWN = (
    DrillDownTarget(
        label="View product",
        target_route="/inventory/products/{product_id}",
        required_permission="inventory.products.read",
        preserves_filters=("warehouse_id",),
    ),
)


def _inventory_list_report(
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
        domain=ReportDomain.INVENTORY,
        authoritative_source=authoritative_source,
        required_permission="reports.inventory.view",
        export_permission="reports.inventory.export",
        domain_capability_key="inventory",
        supported_filters=supported_filters,
        supported_dimensions=supported_dimensions,
        supported_measures=supported_measures,
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=_PRODUCT_DRILL_DOWN,
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


def _inventory_aggregate_report(
    *,
    key: str,
    name: str,
    description: str,
    authoritative_source: str,
    supported_filters: type[BaseModel],
    export_formats: tuple[ExportFormat, ...] = (),
    export_permission: str | None = None,
) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        name=name,
        description=description,
        domain=ReportDomain.INVENTORY,
        authoritative_source=authoritative_source,
        required_permission="reports.inventory.view",
        export_permission=export_permission,
        domain_capability_key="inventory",
        supported_filters=supported_filters,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=export_formats,
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )


register(
    _inventory_aggregate_report(
        key="inventory.summary",
        name="Inventory Summary",
        description="Total stock value by warehouse, category, brand.",
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService."
            "inventory_summary"
        ),
        supported_filters=InventorySummaryFilter,
    )
)

register(
    _inventory_aggregate_report(
        key="inventory.valuation",
        name="Operational Stock Valuation (WAC)",
        description=(
            "On-hand stock costed at Weighted-Average-Cost for operational "
            "purposes; not a reconciled accounting inventory balance."
        ),
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService."
            "inventory_valuation"
        ),
        supported_filters=InventoryValuationFilter,
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        export_permission="reports.inventory.export",
    )
)

register(
    _inventory_list_report(
        # group-by cardinality: warehouse x product per movement; offset-paged
        key="inventory.stock_position",
        name="Stock Position",
        description="On-hand by location.",
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService.stock_ledger"
        ),
        supported_filters=StockPositionFilter,
        supported_dimensions=("warehouse", "product"),
        supported_measures=("quantity",),
    )
)

register(
    _inventory_list_report(
        # group-by cardinality: one row per product/warehouse (<= products x warehouses); offset-paged
        key="inventory.dead_stock",
        name="Dead Stock",
        description="Products with zero movement in the last N days.",
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService.dead_stock"
        ),
        supported_filters=DeadStockFilter,
        supported_dimensions=("product",),
        supported_measures=("total_value",),
    )
)

register(
    _inventory_list_report(
        # group-by cardinality: one row per product (<= tenant products); offset-paged
        key="inventory.movement_velocity",
        name="Movement Velocity",
        description="Fast/slow moving products by movement count over period.",
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService."
            "movement_velocity"
        ),
        supported_filters=MovementVelocityFilter,
        supported_dimensions=("product",),
        supported_measures=("total_movements",),
    )
)

register(
    _inventory_list_report(
        # group-by cardinality: warehouse x product (<= warehouses x products); offset-paged
        key="inventory.stock_aging",
        name="Stock Aging",
        description="Age of current stock by first-receipt date.",
        authoritative_source=(
            "modules.inventory.services.report_service.ReportQueryService.stock_aging"
        ),
        supported_filters=StockAgingFilter,
        supported_dimensions=("warehouse", "product"),
        supported_measures=("age_days",),
    )
)

register(
    _inventory_list_report(
        # group-by cardinality: warehouse x product (<= warehouses x products); offset-paged
        key="inventory.low_stock",
        name="Low Stock Alerts",
        description="Open low-stock/out-of-stock/overstock alerts.",
        authoritative_source=(
            "modules.inventory.repositories.alerts_repository."
            "LowStockAlertRepository.list_for_company"
        ),
        supported_filters=LowStockFilter,
        supported_dimensions=("warehouse", "product"),
        supported_measures=(),
    )
)

register(
    ReportDefinition(
        key="inventory.kpis",
        name="Inventory KPI Dashboard",
        description="10 existing Inventory KPIs.",
        domain=ReportDomain.INVENTORY,
        authoritative_source=(
            "modules.inventory.services.kpi_service.KPIService.compute"
        ),
        required_permission="reports.inventory.view",
        export_permission=None,
        domain_capability_key="inventory",
        supported_filters=InventoryKpiFilter,
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
