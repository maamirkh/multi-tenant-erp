"""Goods Receipt Pydantic schemas — Phase 6.

Schemas:
  GRLineCreate / GRLineUpdate / GRLineRead
  GROpenQuantity        — open quantity per PO line (shown during GR creation)
  GoodsReceiptCreate    — create a new GR against a PO
  GoodsReceiptUpdate    — update GR header fields (DRAFT only)
  GoodsReceiptRead      — full GR detail with lines
  GoodsReceiptListRead  — lightweight for pagination
  GRConfirmRequest      — confirm payload (empty body, id in path)
  GRFilter              — query filters

Spec ref: specs/006-purchase-management/data-model.md §GoodsReceipt Aggregate
Task: T159
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.purchase.schemas.base import PurchaseBaseSchema

GR_STATUSES = ("DRAFT", "CONFIRMED")


# ---------------------------------------------------------------------------
# GRLine schemas
# ---------------------------------------------------------------------------


class GRLineCreate(PurchaseBaseSchema):
    po_line_id: UUID = Field(..., description="POLine being received")
    quantity_received: Decimal = Field(Decimal("0.000"), ge=0)
    quantity_rejected: Decimal = Field(Decimal("0.000"), ge=0)
    rejection_reason_id: UUID | None = None
    unit_cost: Decimal = Field(
        Decimal("0.0000"), ge=0, description="Actual unit cost at receipt"
    )
    notes: str | None = Field(None, max_length=2000)


class GRLineUpdate(PurchaseBaseSchema):
    quantity_received: Decimal | None = Field(None, ge=0)
    quantity_rejected: Decimal | None = Field(None, ge=0)
    rejection_reason_id: UUID | None = None
    unit_cost: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=2000)


class GRLineRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    gr_id: str
    po_line_id: str
    product_id: str | None = None
    quantity_received: Decimal
    quantity_rejected: Decimal
    rejection_reason_id: str | None = None
    unit_cost: Decimal
    po_unit_cost: Decimal
    ppv_amount: Decimal
    ppv_percentage: Decimal
    notes: str | None = None


# ---------------------------------------------------------------------------
# Open quantity helper schema (for GR creation UI)
# ---------------------------------------------------------------------------


class GROpenQuantity(PurchaseBaseSchema):
    """Per-line open quantity display during GR creation."""

    po_line_id: str
    product_description: str
    quantity_ordered: Decimal
    quantity_received_so_far: Decimal
    open_quantity: Decimal
    unit_cost: Decimal


# ---------------------------------------------------------------------------
# GoodsReceipt schemas
# ---------------------------------------------------------------------------


class GoodsReceiptCreate(PurchaseBaseSchema):
    po_id: UUID = Field(..., description="Purchase Order to receive against")
    delivery_note_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    warehouse_id: UUID | None = Field(
        None,
        description="Target warehouse for stock movements (Epic 5). Optional.",
    )
    lines: list[GRLineCreate] = Field(default_factory=list)


class GoodsReceiptUpdate(PurchaseBaseSchema):
    delivery_note_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    warehouse_id: UUID | None = None


class GoodsReceiptRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    gr_number: str
    status: str
    po_id: str
    supplier_id: str
    received_by: str | None = None
    received_at: datetime | None = None
    delivery_note_number: str | None = None
    notes: str | None = None
    warehouse_id: str | None = None
    landed_cost_ready: bool
    lines: list[GRLineRead] = Field(default_factory=list)


class GoodsReceiptListRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    gr_number: str
    status: str
    po_id: str
    supplier_id: str
    received_at: datetime | None = None
    delivery_note_number: str | None = None


# ---------------------------------------------------------------------------
# Action schemas
# ---------------------------------------------------------------------------


class GRConfirmRequest(PurchaseBaseSchema):
    """No additional payload — GR identified by path param."""

    pass


class GRFilter(PurchaseBaseSchema):
    status: str | None = None
    po_id: UUID | None = None
    supplier_id: UUID | None = None
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)
