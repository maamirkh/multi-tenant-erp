"""Purchase Order Pydantic schemas — Phase 5.

Schemas:
  POLineCreate / POLineUpdate / POLineRead
  POAdditionalChargeCreate / POAdditionalChargeUpdate / POAdditionalChargeRead
  POAmendmentRead
  PurchaseOrderCreate / PurchaseOrderUpdate / PurchaseOrderRead
  PurchaseOrderListRead  — lightweight list for pagination
  POSubmitRequest
  POAmendRequest
  POCancelRequest
  POCloseRequest
  POFilter

Spec ref: specs/006-purchase-management/spec.md §23 Functional Requirements
Task: T138
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PurchaseBaseSchema

PO_STATUSES = (
    "DRAFT",
    "PENDING_APPROVAL",
    "APPROVED",
    "PARTIALLY_RECEIVED",
    "FULLY_RECEIVED",
    "CLOSED",
    "CANCELLED",
)

CHARGE_TYPES = ("FREIGHT", "HANDLING", "INSURANCE", "OTHER")


# ---------------------------------------------------------------------------
# POLine schemas
# ---------------------------------------------------------------------------


class POLineCreate(PurchaseBaseSchema):
    pr_line_id: UUID | None = Field(
        None, description="Originating PR line (if from PR conversion)"
    )
    product_id: UUID | None = Field(
        None, description="Optional product catalog reference"
    )
    product_description: str = Field(..., min_length=1, max_length=500)
    quantity_ordered: Decimal = Field(..., gt=0, description="Must be > 0")
    uom_id: UUID | None = Field(None, description="Optional unit of measure")
    unit_cost: Decimal = Field(Decimal("0.0000"), ge=0, description="Must be >= 0")
    line_discount_percent: Decimal | None = Field(None, ge=0, le=100)
    line_discount_amount: Decimal | None = Field(None, ge=0)
    tax_code: str | None = Field(
        None, max_length=50, description="Tax code — tax readiness"
    )
    tax_rate: Decimal | None = Field(None, ge=0, le=100, description="Tax rate %")
    tax_amount: Decimal | None = Field(None, ge=0, description="Tax amount")
    notes: str | None = Field(None, max_length=2000)


class POLineUpdate(PurchaseBaseSchema):
    product_description: str | None = Field(None, min_length=1, max_length=500)
    quantity_ordered: Decimal | None = Field(None, gt=0)
    unit_cost: Decimal | None = Field(None, ge=0)
    line_discount_percent: Decimal | None = Field(None, ge=0, le=100)
    line_discount_amount: Decimal | None = Field(None, ge=0)
    tax_code: str | None = Field(None, max_length=50)
    tax_rate: Decimal | None = Field(None, ge=0, le=100)
    tax_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=2000)


class POLineRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    po_id: str
    pr_line_id: str | None = None
    line_number: int
    product_id: str | None = None
    product_description: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_rejected: Decimal
    open_quantity: Decimal
    uom_id: str | None = None
    unit_cost: Decimal
    line_discount_percent: Decimal | None = None
    line_discount_amount: Decimal | None = None
    line_total: Decimal
    tax_code: str | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# POAdditionalCharge schemas
# ---------------------------------------------------------------------------


class POAdditionalChargeCreate(PurchaseBaseSchema):
    charge_type: str = Field(..., description="FREIGHT / HANDLING / INSURANCE / OTHER")
    description: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., ge=0)

    @field_validator("charge_type")
    @classmethod
    def validate_charge_type(cls, v: str) -> str:
        if v not in CHARGE_TYPES:
            raise ValueError(f"charge_type must be one of {CHARGE_TYPES}")
        return v


class POAdditionalChargeUpdate(PurchaseBaseSchema):
    description: str | None = Field(None, min_length=1, max_length=200)
    amount: Decimal | None = Field(None, ge=0)


class POAdditionalChargeRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    po_id: str
    charge_type: str
    description: str
    amount: Decimal


# ---------------------------------------------------------------------------
# POAmendment schema (read only — append-only)
# ---------------------------------------------------------------------------


class POAmendmentRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    po_id: str
    amendment_number: int
    reason: str
    change_summary: dict | None = None
    requested_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    status: str
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# PurchaseOrder schemas
# ---------------------------------------------------------------------------


class PurchaseOrderCreate(PurchaseBaseSchema):
    supplier_id: UUID | None = Field(
        None, description="Supplier — required before submission"
    )
    purchase_request_id: UUID | None = Field(
        None, description="Originating PR (if applicable)"
    )
    payment_terms_id: UUID | None = None
    expected_delivery_date: date | None = None
    supplier_reference: str | None = Field(None, max_length=100)
    currency_code: str = Field("USD", min_length=3, max_length=3)
    notes: str | None = None
    lines: list[POLineCreate] = Field(default_factory=list)


class PurchaseOrderUpdate(PurchaseBaseSchema):
    supplier_id: UUID | None = None
    payment_terms_id: UUID | None = None
    expected_delivery_date: date | None = None
    supplier_reference: str | None = Field(None, max_length=100)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    notes: str | None = None


class PurchaseOrderRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    po_number: str
    status: str
    supplier_id: str | None = None
    purchase_request_id: str | None = None
    payment_terms_id: str | None = None
    expected_delivery_date: date | None = None
    supplier_reference: str | None = None
    currency_code: str
    subtotal: Decimal
    total_charges: Decimal
    total_discounts: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: str | None = None
    version: int
    lines: list[POLineRead] = Field(default_factory=list)
    charges: list[POAdditionalChargeRead] = Field(default_factory=list)
    amendments: list[POAmendmentRead] = Field(default_factory=list)


class PurchaseOrderListRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    po_number: str
    status: str
    supplier_id: str | None = None
    expected_delivery_date: date | None = None
    currency_code: str
    total: Decimal
    version: int


# ---------------------------------------------------------------------------
# Action request payloads
# ---------------------------------------------------------------------------


class POSubmitRequest(PurchaseBaseSchema):
    """No additional payload needed — PO identified by path param."""

    pass


class POAmendRequest(PurchaseBaseSchema):
    reason: str = Field(
        ..., min_length=1, description="Justification for this amendment"
    )
    changes: dict = Field(..., description="Map of field names to new values")


class POCancelRequest(PurchaseBaseSchema):
    reason_code_id: UUID | None = Field(None, description="Cancellation reason code")
    reason: str | None = Field(None, max_length=500)
    cancellation_reason: str | None = Field(None, max_length=500)
    has_confirmed_gr: bool = Field(
        False,
        description="Set True when a confirmed GR exists — blocks cancellation",
    )


class POCloseRequest(PurchaseBaseSchema):
    """No additional payload required."""

    pass


class POFilter(PurchaseBaseSchema):
    status: str | None = None
    statuses: list[str] | None = None
    supplier_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)
