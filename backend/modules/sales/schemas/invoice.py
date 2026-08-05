"""Sales Invoice Pydantic schemas — Phase 6.

Schemas:
  InvoiceLineCreate    — create an invoice line
  InvoiceLineRead      — full line response
  InvoiceChargeCreate  — create an additional charge
  InvoiceChargeRead    — full charge response
  InvoiceCreate        — create a new invoice (DRAFT)
  InvoiceIssueRequest  — transition DRAFT → ISSUED
  InvoiceRead          — full invoice response
  InvoiceListItem      — minimal representation for list views
  InvoiceListResponse  — paginated list wrapper

Spec ref: specs/007-sales-management/plan.md §API Contracts
Task: T171
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import field_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# InvoiceLine schemas
# ---------------------------------------------------------------------------


class InvoiceLineCreate(SalesBaseSchema):
    product_id: UUID | None = None
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    discount_percentage: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_rate: Decimal | None = None
    delivery_note_line_id: UUID | None = None
    order_line_id: UUID | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("unit_price cannot be negative")
        return v


class InvoiceLineRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    invoice_id: str
    line_number: int
    product_id: str | None
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    discount_percentage: Decimal | None
    discount_amount: Decimal | None
    tax_rate: Decimal | None
    tax_amount: Decimal
    extended_amount: Decimal
    delivery_note_line_id: str | None
    order_line_id: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# InvoiceCharge schemas
# ---------------------------------------------------------------------------


class InvoiceChargeCreate(SalesBaseSchema):
    charge_type: Literal["FREIGHT", "HANDLING", "INSURANCE", "OTHER"]
    description: str
    amount: Decimal
    tax_applicable: bool = False

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class InvoiceChargeRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    invoice_id: str
    charge_type: str
    description: str
    amount: Decimal
    tax_applicable: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# SalesInvoice create / update
# ---------------------------------------------------------------------------


class InvoiceCreate(SalesBaseSchema):
    """Payload for creating a new SalesInvoice in DRAFT status.

    Supports three creation modes:
      - from_delivery_note_id: invoice from DN delivered quantities
      - from_order_id: invoice from approved SO ordered quantities
      - manual: invoice with explicit lines (requires specific permission)
    """

    customer_id: UUID
    order_id: UUID | None = None
    delivery_note_id: UUID | None = None
    invoice_date: str  # ISO 8601: YYYY-MM-DD
    currency_code: str
    payment_term_id: UUID | None = None
    billing_address_id: UUID | None = None
    internal_notes: str | None = None
    customer_notes: str | None = None
    lines: list[InvoiceLineCreate] = []
    charges: list[InvoiceChargeCreate] = []

    @field_validator("invoice_date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        from datetime import date

        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(
                f"invoice_date must be ISO 8601 (YYYY-MM-DD): {v}"
            ) from exc
        return v


class InvoiceIssueRequest(SalesBaseSchema):
    """Payload for transitioning a DRAFT invoice to ISSUED."""

    issued_by: UUID | None = None


class InvoiceCreditNoteRequest(SalesBaseSchema):
    """Payload for issuing a credit note against an ISSUED invoice."""

    credit_note_amount: Decimal
    issued_by: UUID | None = None
    notes: str | None = None

    @field_validator("credit_note_amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("credit_note_amount must be positive")
        return v


# ---------------------------------------------------------------------------
# SalesInvoice read schemas
# ---------------------------------------------------------------------------


class InvoiceRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    invoice_number: str
    customer_id: str
    order_id: str | None
    delivery_note_id: str | None
    payment_term_id: str | None
    billing_address_id: str | None
    invoice_date: str
    due_date: str
    currency_code: str
    status: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    charges_amount: Decimal
    total_amount: Decimal
    amount_in_words: str | None
    credit_note_amount: Decimal | None
    internal_notes: str | None
    customer_notes: str | None
    version: int
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class InvoiceListItem(SalesBaseSchema):
    id: UUID
    invoice_number: str
    customer_id: str
    order_id: str | None
    status: str
    invoice_date: str
    due_date: str
    total_amount: Decimal
    currency_code: str
    created_at: datetime | None


class InvoiceListResponse(SalesBaseSchema):
    items: list[InvoiceListItem]
    total: int
    limit: int
    offset: int
