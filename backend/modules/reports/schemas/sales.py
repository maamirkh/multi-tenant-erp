"""Sales report filter/response schemas (spec §14, plan.md Phase 2 §2.2).

No ``branch_id`` — Sales carries no ``branch_id`` column on any model
(FR-RPT-162). Filter schemas translate 1:1 into
``modules.sales.schemas.reports.ReportParams`` at the adapter boundary;
row shapes mirror ``ReportService``'s own per-report-type dict output
exactly (no re-derived calculation, FR-RPT-053).
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.sales.schemas.reports import KPIResult


class _SalesDateRangeFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: _date | None = None
    date_to: _date | None = None


class SalesSummaryFilter(_SalesDateRangeFilter):
    customer_id: str | None = None


class SalesByCustomerFilter(_SalesDateRangeFilter):
    pass


class SalesByProductFilter(_SalesDateRangeFilter):
    customer_id: str | None = None


class TopCustomersFilter(_SalesDateRangeFilter):
    limit: int = 10


class SalesTrendFilter(_SalesDateRangeFilter):
    pass


class QuotationPipelineFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None


class SalesReturnsFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    status: str | None = None
    order_id: str | None = None
    resolution_type: str | None = None


class SalesKpiFilter(_SalesDateRangeFilter):
    pass


# ---------------------------------------------------------------------------
# Response row shapes — mirror ReportService's own dict keys per report type.
# Revenue aggregates carry ``currency_code``: one row per currency, never a
# cross-currency sum (FR-RPT-152).
# ---------------------------------------------------------------------------


class SalesSummaryRow(BaseModel):
    date: _date | None = None
    invoice_count: int
    revenue: Decimal
    total_discount: Decimal
    currency_code: str | None = None


class SalesByCustomerRow(BaseModel):
    customer_id: str | None = None
    customer_name: str
    """Defensively resolved display name (FR-RPT-053) — set to the literal
    string ``"[unavailable reference]"`` at the adapter boundary if
    ``customer_id`` doesn't resolve to an existing Customer (no DB-level
    FK enforces this reference, so a dangling ID is a real, expected case,
    never an error)."""
    invoice_count: int
    revenue: Decimal
    currency_code: str | None = None


class SalesByProductRow(BaseModel):
    product_id: str | None = None
    description: str | None = None
    revenue: Decimal
    total_qty: Decimal
    line_count: int
    currency_code: str | None = None


class QuotationPipelineRow(BaseModel):
    id: str
    quotation_number: str
    customer_id: str | None = None
    quotation_date: _date | None = None
    validity_date: _date | None = None
    status: str
    total_amount: Decimal


class SalesReturnRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    return_number: str
    customer_id: str
    order_id: str | None = None
    return_date: str
    status: str
    resolution_type: str


class SalesCurrencyKpis(BaseModel):
    currency_code: str
    kpis: list[KPIResult]


class SalesKpiReport(BaseModel):
    """``sales.kpis`` (FR-RPT-152): the count, rate and time KPIs once, and
    Sales' money KPIs (``MONEY_KPI_IDS``) once per currency present — never
    one figure summed across currencies."""

    company_id: str
    period_label: str
    kpis: list[KPIResult]
    by_currency: list[SalesCurrencyKpis]
