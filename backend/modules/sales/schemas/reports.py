"""Pydantic v2 schemas for Sales Intelligence & Reporting — Phase 8.

Covers:
  - KPIResult / KPIDashboard
  - ReportRow (generic dict-based row)
  - ReportResponse (paginated or full)
  - ReportParams (query filters shared across report types)
  - ExportFormat

25 report types enumerated in ReportType.
12 KPI identifiers enumerated in KPIType.

Task: T213
Spec ref: specs/007-sales-management/spec.md §35–§36
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ReportType(str, Enum):
    # Sales Reports
    SALES_SUMMARY = "sales_summary"
    SALES_BY_CUSTOMER = "sales_by_customer"
    SALES_BY_PRODUCT = "sales_by_product"
    SALES_BY_REPRESENTATIVE = "sales_by_representative"
    SALES_ORDER_PIPELINE = "sales_order_pipeline"
    SALES_VS_TARGET = "sales_vs_target"
    TOP_CUSTOMERS = "top_customers"
    SALES_TREND = "sales_trend"

    # Customer Reports
    CUSTOMER_LIST = "customer_list"
    CUSTOMER_AGEING = "customer_ageing"
    CUSTOMER_ACTIVITY = "customer_activity"
    NEW_CUSTOMERS = "new_customers"
    CUSTOMER_CREDIT_REPORT = "customer_credit_report"

    # Quotation Reports
    QUOTATION_CONVERSION_RATE = "quotation_conversion_rate"
    QUOTATION_PIPELINE = "quotation_pipeline"
    EXPIRED_QUOTATIONS = "expired_quotations"

    # Delivery Reports
    PENDING_DELIVERIES = "pending_deliveries"
    DELIVERY_PERFORMANCE = "delivery_performance"
    BACKORDER_REPORT = "backorder_report"

    # Profitability Reports
    GROSS_MARGIN_BY_PRODUCT = "gross_margin_by_product"
    GROSS_MARGIN_BY_CUSTOMER = "gross_margin_by_customer"
    DISCOUNT_ANALYSIS = "discount_analysis"

    # Audit Reports
    SALES_AUDIT_TRAIL = "sales_audit_trail"
    PRICE_OVERRIDE_REPORT = "price_override_report"
    CREDIT_LIMIT_CHANGE_REPORT = "credit_limit_change_report"
    APPROVAL_HISTORY = "approval_history"


class KPIType(str, Enum):
    REVENUE = "KPI-01"
    GROSS_MARGIN_PCT = "KPI-02"
    QUOTATION_CONVERSION_RATE = "KPI-03"
    AOV = "KPI-04"
    SALES_GROWTH_RATE = "KPI-05"
    CUSTOMER_RETENTION_RATE = "KPI-06"
    ON_TIME_DELIVERY_RATE = "KPI-07"
    OUTSTANDING_ORDERS_VALUE = "KPI-08"
    RETURN_RATE = "KPI-09"
    AVG_DAYS_TO_FULFIL = "KPI-10"
    CREDIT_UTILISATION = "KPI-11"
    INVOICE_CYCLE_TIME = "KPI-12"


class ExportFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"


# ---------------------------------------------------------------------------
# Report parameters (shared filters)
# ---------------------------------------------------------------------------


class ReportParams(BaseModel):
    """Common query parameters for all report endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    date_from: str | None = Field(
        default=None,
        description="Start date filter (ISO 8601 YYYY-MM-DD)",
    )
    date_to: str | None = Field(
        default=None,
        description="End date filter (ISO 8601 YYYY-MM-DD)",
    )
    customer_id: str | None = Field(default=None, description="Filter by customer UUID")
    sales_rep_id: str | None = Field(
        default=None, description="Filter by sales representative UUID"
    )
    currency_code: str | None = Field(
        default=None, description="Filter by currency code (e.g. USD)"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


# ---------------------------------------------------------------------------
# KPI schemas
# ---------------------------------------------------------------------------


class KPIResult(BaseModel):
    """Single KPI value with metadata."""

    model_config = ConfigDict(populate_by_name=True)

    kpi_id: str = Field(description="KPI identifier (e.g. KPI-01)")
    name: str = Field(description="Human-readable KPI name")
    value: Decimal | None = Field(
        description="Computed KPI value; null if insufficient data"
    )
    unit: str = Field(description="Unit label (e.g. USD, %, days)")
    period_label: str = Field(description="Period the KPI covers (e.g. 2026-08)")
    trend: str | None = Field(
        default=None,
        description="UP | DOWN | STABLE compared to previous period",
    )
    change_pct: Decimal | None = Field(
        default=None,
        description="Percentage change vs previous period",
    )


class KPIDashboard(BaseModel):
    """Full KPI dashboard response for a company and period."""

    model_config = ConfigDict(populate_by_name=True)

    company_id: str
    period_label: str
    kpis: list[KPIResult]


# ---------------------------------------------------------------------------
# Report response schemas
# ---------------------------------------------------------------------------


class ReportRow(BaseModel):
    """Generic report row — flexible dict of column → value."""

    model_config = ConfigDict(populate_by_name=True)

    data: dict[str, Any]


class ReportResponse(BaseModel):
    """Paginated report response."""

    model_config = ConfigDict(populate_by_name=True)

    report_type: str
    company_id: str
    params: dict[str, Any]
    total: int
    rows: list[dict[str, Any]]
