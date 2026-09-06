"""Vendor Return (RMA) Pydantic schemas — Phase 7.

Schemas:
  ReturnLineCreate / ReturnLineRead
  VendorReturnCreate    — create a new RMA against a confirmed GR
  VendorReturnUpdate    — update RMA header fields (DRAFT only)
  VendorReturnRead      — full RMA detail with lines
  VendorReturnListRead  — lightweight for pagination
  RMAFilter             — query filters

Spec ref: specs/006-purchase-management/data-model.md §VendorReturn Aggregate
Task: T180
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.purchase.schemas.base import PurchaseBaseSchema

RMA_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "DISPATCHED",
    "COMPLETED",
    "CANCELLED",
)


# ---------------------------------------------------------------------------
# ReturnLine schemas
# ---------------------------------------------------------------------------


class ReturnLineCreate(PurchaseBaseSchema):
    gr_line_id: UUID = Field(..., description="GRLine being returned")
    quantity_returned: Decimal = Field(Decimal("0.000"), ge=0)
    reason_id: UUID | None = Field(None, description="Line-level return reason code")
    notes: str | None = Field(None, max_length=2000)


class ReturnLineRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    return_id: str
    gr_line_id: str
    product_id: str | None = None
    quantity_returned: Decimal
    reason_id: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# VendorReturn schemas
# ---------------------------------------------------------------------------


class VendorReturnCreate(PurchaseBaseSchema):
    gr_id: UUID = Field(..., description="Confirmed GoodsReceipt to return against")
    reason_id: UUID | None = Field(None, description="Overall return reason code")
    notes: str | None = None
    lines: list[ReturnLineCreate] = Field(default_factory=list)


class VendorReturnUpdate(PurchaseBaseSchema):
    reason_id: UUID | None = None
    notes: str | None = None
    replacement_po_id: UUID | None = Field(
        None,
        description="Optional replacement PO linkage — does not affect RMA state",
    )


class VendorReturnRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    rma_number: str
    status: str
    gr_id: str
    supplier_id: str
    initiated_by: str | None = None
    reason_id: str | None = None
    notes: str | None = None
    replacement_po_id: str | None = None
    credit_note_pending: bool
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    lines: list[ReturnLineRead] = Field(default_factory=list)


class VendorReturnListRead(PurchaseBaseSchema):
    id: UUID
    company_id: UUID
    rma_number: str
    status: str
    gr_id: str
    supplier_id: str
    credit_note_pending: bool
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Filter schema
# ---------------------------------------------------------------------------


class RMAFilter(PurchaseBaseSchema):
    status: str | None = None
    gr_id: UUID | None = None
    supplier_id: UUID | None = None
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)
