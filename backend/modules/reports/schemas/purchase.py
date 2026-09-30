"""Purchase report filter/response schemas (spec §15, plan.md Phase 2
§2.3). ``branch_id`` is optional only on ``OpenCommitmentsFilter``/
``PendingDeliveriesFilter`` (FR-RPT-062) — ``PurchaseOrder`` carries a
nullable, unconstrained ``branch_id`` column reserved for future
branch-linkage (data filter only, never authorization, §25).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PurchaseSummaryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    supplier_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class PurchaseBySupplierFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


class SupplierPerformanceFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


class OpenCommitmentsFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID | None = None
    branch_id: UUID | None = None


class PendingDeliveriesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date | None = None
    branch_id: UUID | None = None


class VendorReturnsFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    supplier_id: UUID | None = None


class PurchaseKpiFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None


# ---------------------------------------------------------------------------
# Response row shapes — mirror ReportService's own dict keys per report.
# ---------------------------------------------------------------------------


class PurchaseOrderSummaryRow(BaseModel):
    po_id: str
    po_number: str
    status: str
    supplier_id: str | None = None
    currency_code: str
    subtotal: Decimal
    total_charges: Decimal
    total_discounts: Decimal
    tax_amount: Decimal
    total: Decimal
    expected_delivery_date: str | None = None
    created_at: str | None = None


class PurchaseBySupplierRow(BaseModel):
    supplier_id: str | None = None
    gr_count: int
    total_spend: Decimal
    total_subtotal: Decimal
    total_charges: Decimal
    total_discounts: Decimal
    currency_code: str | None = None
    """One row per supplier and currency — spend in different currencies is
    never summed together (FR-RPT-152)."""


class SupplierPerformanceRow(BaseModel):
    supplier_id: str
    total_grs: int
    on_time_rate: float
    fill_rate: float
    rejection_rate: float
    composite_rating: float


class OpenCommitmentRow(BaseModel):
    po_line_id: str
    po_id: str | None = None
    po_number: str
    supplier_id: str | None = None
    currency_code: str
    product_description: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    open_quantity: Decimal
    unit_cost: Decimal
    open_value: Decimal
    expected_delivery_date: str | None = None


class PendingDeliveryRow(BaseModel):
    po_id: str
    po_number: str
    status: str
    supplier_id: str | None = None
    total: Decimal
    currency_code: str
    expected_delivery_date: str
    days_overdue: int


class PurchaseCurrencyAmounts(BaseModel):
    currency_code: str
    open_commitments_value: Decimal
    total_purchase_value: Decimal


class PurchaseKpiSet(BaseModel):
    """11 existing Purchase KPIs (``KPIService.get_all_kpis()``) — a
    loosely-typed pass-through wrapper, since the source returns a mix of
    numeric/string-Decimal values under 10 differently-shaped keys not
    worth hand-declaring field-by-field for this catalog wrapper.

    The two money KPIs (Purchase's ``MONEY_KPI_KEYS``) are not passed
    through, because the source sums them across currencies; ``by_currency``
    carries them per currency instead (FR-RPT-152)."""

    model_config = ConfigDict(extra="allow")

    by_currency: list[PurchaseCurrencyAmounts]


class VendorReturnRow(BaseModel):
    rma_id: str
    rma_number: str
    status: str
    gr_id: str | None = None
    supplier_id: str | None = None
    reason_id: str | None = None
    credit_note_pending: bool | None = None
    dispatched_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
