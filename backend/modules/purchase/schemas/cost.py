"""Purchase Costing Pydantic schemas — Phase 8.

Schemas:
  PPVLine            — PPV data per GR line
  GRCostSummary      — cost breakdown for a single Goods Receipt
  POCostSummary      — cost breakdown for a Purchase Order (aggregated from PO data)
  PurchaseCostEntryRead — read-only view of a PurchaseCostEntry

Spec ref: specs/006-purchase-management/spec.md §19 Purchase Costing
Task: T199
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class PPVLine(BaseModel):
    """PPV data for a single GR line."""

    model_config = ConfigDict(from_attributes=True)

    gr_line_id: str
    po_line_id: str
    product_id: str | None = None
    quantity_received: Decimal
    unit_cost: Decimal
    po_unit_cost: Decimal
    ppv_amount: Decimal
    ppv_percentage: Decimal

    @field_validator(
        "quantity_received",
        "unit_cost",
        "po_unit_cost",
        "ppv_amount",
        "ppv_percentage",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


class GRCostSummary(BaseModel):
    """Cost summary for a single Goods Receipt, including PPV per line."""

    model_config = ConfigDict(from_attributes=True)

    gr_id: str
    gr_number: str
    po_id: str
    supplier_id: str
    status: str
    subtotal: Decimal
    ppv_lines: list[PPVLine]
    total_ppv_amount: Decimal


class POCostSummary(BaseModel):
    """Cost summary for a Purchase Order — header financial fields."""

    model_config = ConfigDict(from_attributes=True)

    po_id: str
    po_number: str
    supplier_id: str | None = None
    status: str
    currency_code: str
    subtotal: Decimal
    total_charges: Decimal
    total_discounts: Decimal
    tax_amount: Decimal
    total: Decimal

    @field_validator(
        "subtotal",
        "total_charges",
        "total_discounts",
        "tax_amount",
        "total",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


class PurchaseCostEntryRead(BaseModel):
    """Read-only view of a PurchaseCostEntry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    gr_id: str
    po_id: str
    supplier_id: str
    cost_date: date
    subtotal: Decimal
    total_charges: Decimal
    total_discounts: Decimal
    tax_amount: Decimal
    total: Decimal
    credit_note_pending: bool
    invoice_id: str | None = None
    currency_code: str
    created_at: datetime

    @field_validator(
        "subtotal",
        "total_charges",
        "total_discounts",
        "tax_amount",
        "total",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))
