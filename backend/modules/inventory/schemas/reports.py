"""Pydantic schemas for inventory reporting — Phase 9.

Covers all 14 inventory reports and the 10-KPI dashboard response.

Spec ref: specs/005-inventory-management/spec.md §32–§33
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _ReportBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Report 1 — Inventory Summary
# =============================================================================


class InventorySummaryRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    category_name: str | None = None
    brand_name: str | None = None
    warehouse_id: str
    warehouse_name: str
    qty_on_hand: Decimal
    unit_cost: Decimal | None = None
    total_value: Decimal
    currency_code: str | None = None


class InventorySummaryReport(_ReportBase):
    rows: list[InventorySummaryRow]
    grand_total_value: Decimal
    as_of: datetime


# =============================================================================
# Report 2 — Stock Ledger
# =============================================================================


class StockLedgerRow(_ReportBase):
    movement_id: str
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    movement_type: str
    direction: str
    quantity: Decimal
    unit_cost: Decimal | None = None
    total_value: Decimal | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    performed_at: datetime
    notes: str | None = None


class StockLedgerReport(_ReportBase):
    rows: list[StockLedgerRow]
    total_rows: int


# =============================================================================
# Report 3 — Inventory Valuation
# =============================================================================


class ValuationRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    total_qty: Decimal
    unit_cost: Decimal | None = None
    total_value: Decimal
    currency_code: str | None = None
    valuation_method: str


class InventoryValuationReport(_ReportBase):
    rows: list[ValuationRow]
    grand_total_value: Decimal
    currency_code: str | None = None
    as_of: datetime


# =============================================================================
# Report 4 — Stock Position
# =============================================================================


class StockPositionRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    qty_on_hand: Decimal
    qty_reserved: Decimal
    qty_damaged: Decimal
    qty_available: Decimal
    reorder_level: Decimal
    safety_stock: Decimal
    is_below_reorder: bool
    is_below_safety: bool
    is_out_of_stock: bool


class StockPositionReport(_ReportBase):
    rows: list[StockPositionRow]
    total_rows: int


# =============================================================================
# Report 5 — Warehouse Utilisation
# =============================================================================


class WarehouseUtilisationRow(_ReportBase):
    warehouse_id: str
    warehouse_name: str
    warehouse_code: str
    total_products: int
    total_qty_on_hand: Decimal
    total_value: Decimal
    active_locations: int
    used_locations: int


class WarehouseUtilisationReport(_ReportBase):
    rows: list[WarehouseUtilisationRow]


# =============================================================================
# Reports 6 & 7 — Category/Brand Performance
# =============================================================================


class CategoryReportRow(_ReportBase):
    category_id: str | None
    category_name: str
    total_products: int
    total_qty_on_hand: Decimal
    total_value: Decimal
    total_movements: int


class BrandReportRow(_ReportBase):
    brand_id: str | None
    brand_name: str
    total_products: int
    total_qty_on_hand: Decimal
    total_value: Decimal
    total_movements: int


class CategoryBrandReport(_ReportBase):
    categories: list[CategoryReportRow]
    brands: list[BrandReportRow]


# =============================================================================
# Report 8 — Dead Stock
# =============================================================================


class DeadStockRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    qty_on_hand: Decimal
    total_value: Decimal
    last_movement_at: datetime | None
    days_without_movement: int


class DeadStockReport(_ReportBase):
    rows: list[DeadStockRow]
    threshold_days: int
    total_dead_stock_value: Decimal


# =============================================================================
# Reports 9 & 10 — Movement Velocity (Fast/Slow Moving)
# =============================================================================


class MovementVelocityRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    total_movements: int
    total_quantity_moved: Decimal
    avg_daily_movement: Decimal
    first_movement_at: datetime | None
    last_movement_at: datetime | None


class MovementVelocityReport(_ReportBase):
    fast_moving: list[MovementVelocityRow]
    slow_moving: list[MovementVelocityRow]
    period_days: int


# =============================================================================
# Report 11 — Stock Aging
# =============================================================================


class StockAgingRow(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    qty_on_hand: Decimal
    first_receipt_at: datetime | None
    age_days: int | None
    bucket: str  # e.g. "0-30", "31-60", "61-90", "90+"


class StockAgingReport(_ReportBase):
    rows: list[StockAgingRow]
    as_of: datetime


# =============================================================================
# Reports 12 & 13 — Operational (Adjustment + Transfer)
# =============================================================================


class AdjustmentReportRow(_ReportBase):
    adjustment_id: str
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal | None = None
    status: str
    created_at: datetime
    notes: str | None = None


class TransferReportRow(_ReportBase):
    transfer_id: str
    reference_no: str | None
    source_warehouse_id: str
    source_warehouse_name: str
    destination_warehouse_id: str
    destination_warehouse_name: str
    status: str
    total_lines: int
    created_at: datetime
    dispatched_at: datetime | None
    received_at: datetime | None


class OperationalReport(_ReportBase):
    adjustments: list[AdjustmentReportRow]
    transfers: list[TransferReportRow]


# =============================================================================
# Report 14 — Inventory Trend Analysis
# =============================================================================


class TrendDataPoint(_ReportBase):
    date: datetime
    qty_on_hand: Decimal
    total_in: Decimal
    total_out: Decimal
    net_change: Decimal


class TrendAnalysisReport(_ReportBase):
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str | None
    warehouse_name: str | None
    data_points: list[TrendDataPoint]
    period_start: datetime
    period_end: datetime


# =============================================================================
# KPI Dashboard
# =============================================================================


class KPIDashboard(_ReportBase):
    inventory_turnover: Decimal = Field(
        description="Cost of goods sold / average inventory value"
    )
    average_inventory_value: Decimal = Field(
        description="Average inventory value over the period"
    )
    inventory_accuracy: Decimal = Field(
        description="% of products with no variance (proxy: % with non-zero cost)"
    )
    dead_stock_percentage: Decimal = Field(
        description="% of stock by value with no movement in last 90 days"
    )
    stock_accuracy_percentage: Decimal = Field(
        description="% of positions with qty_on_hand above 0"
    )
    warehouse_efficiency: Decimal = Field(description="% of warehouses that are ACTIVE")
    total_inventory_value: Decimal = Field(
        description="Current total inventory value across all warehouses"
    )
    reorder_frequency: Decimal = Field(
        description="Number of reorder suggestions created in the period"
    )
    stockout_rate: Decimal = Field(description="% of products with qty_on_hand == 0")
    overstock_rate: Decimal = Field(
        description="% of positions with qty_on_hand > maximum_stock (where maximum_stock is set)"
    )
    as_of: datetime
    period_days: int = Field(
        description="Lookback period in days used for rate calculations"
    )


# =============================================================================
# Export response
# =============================================================================


class ExportResponse(_ReportBase):
    download_url: str
    file_name: str
    format: str  # "csv" or "xlsx"
    row_count: int
